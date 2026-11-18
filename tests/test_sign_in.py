"""Tests for the sign-in screen of a copy that has an invite code set.

The page is run without a browser (Streamlit's AppTest). The accounts are
made-up people in a store held in RAM.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from langgraph.store.memory import InMemoryStore
from streamlit.testing.v1 import AppTest

from agent import accounts
from tests.test_app import make_runtime

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CODE = "open sesame"
PASSWORD = "correct horse battery"
START_TITLE = "Research **any market**."


def no_agent(*args, **kwargs):
    raise AssertionError("the agent was created before anyone signed in")


@pytest.fixture
def site(tmp_path):
    """A copy of the app with an invite code set. site.visit() opens the
    page in a new browser session; site.store holds the accounts.

    The agent is only available after site.allow_agent(): a test that does
    not call it proves that nothing is created before someone signs in.
    """
    class Site:
        store = InMemoryStore()
        runtime = None

        def allow_agent(self, replies=None, model=None):
            """Make the agent available. It shares the store that holds
            the accounts, as the real app does."""
            self.runtime = make_runtime(tmp_path, replies or [], model=model, store=self.store)

        def visit(self):
            return AppTest.from_file(APP, default_timeout=30).run()

    site = Site()

    def get_runtime(*args, **kwargs):
        return site.runtime or no_agent()

    with patch("agent.config.APP_PASSWORD", CODE), \
            patch("ui.runtime.get_store", lambda: site.store), \
            patch("ui.runtime.get_runtime", get_runtime):
        yield site
    if site.runtime:
        site.runtime.checkpointer.conn.close()


def fill(app, **values):
    """Type into the fields with these keys."""
    for key, value in values.items():
        app.text_input(key=key).set_value(value)
    return app


def press(app, label: str):
    next(button for button in app.button if button.label == label).click().run()
    return app


def errors(app) -> list[str]:
    return [error.value for error in app.error]


def sign_in(app, username: str, password: str):
    return press(fill(app, sign_in_username=username, sign_in_password=password), "Sign in")


def create(app, name="Anna", username="anna", password=PASSWORD, code=CODE,
           email="anna@example.com"):
    fill(app, create_name=name, create_username=username, create_email=email,
         create_password=password, create_code=code)
    return press(app, "Create account")


# --- before signing in -------------------------------------------------------------------------

def test_with_an_invite_code_set_only_the_sign_in_screen_is_shown(site):
    app = site.visit()

    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]
    assert len(app.chat_input) == 0                       # no question box yet
    assert not [b for b in app.button if (b.key or "").startswith("card_")]


def test_the_password_fields_hide_what_is_typed(site):
    app = site.visit()

    assert app.text_input(key="sign_in_password").proto.type == 1      # 1 = password
    assert app.text_input(key="create_password").proto.type == 1
    assert app.text_input(key="create_code").proto.type == 1


# --- signing in --------------------------------------------------------------------------------

def test_an_account_signs_in_and_the_app_opens(site):
    accounts.create_account(site.store, "anna", "Anna", PASSWORD)
    site.allow_agent()

    app = sign_in(site.visit(), "anna", PASSWORD)

    assert not app.exception
    assert app.title[0].value == START_TITLE
    assert app.session_state["account"] == {"username": "anna", "name": "Anna"}


def test_a_wrong_password_is_refused(site):
    accounts.create_account(site.store, "anna", "Anna", PASSWORD)

    app = sign_in(site.visit(), "anna", "a wrong password")

    assert not app.exception
    assert errors(app) == ["That username and password don't match. Try again."]
    assert len(app.chat_input) == 0
    assert "account" not in app.session_state


def test_after_five_wrong_tries_the_page_says_to_wait(site):
    accounts.create_account(site.store, "anna", "Anna", PASSWORD)
    app = site.visit()
    for _ in range(5):
        sign_in(app, "anna", "a wrong password")

    sign_in(app, "anna", PASSWORD)

    assert errors(app) == ["Too many wrong tries. Wait a minute and try again."]
    assert "account" not in app.session_state


def test_each_browser_session_signs_in_for_itself(site):
    accounts.create_account(site.store, "anna", "Anna", PASSWORD)
    site.allow_agent()
    sign_in(site.visit(), "anna", PASSWORD)

    someone_else = site.visit()

    assert len(someone_else.chat_input) == 0
    assert "account" not in someone_else.session_state


# --- creating an account -------------------------------------------------------------------------

def test_an_account_created_with_the_invite_code_is_signed_in_at_once(site):
    site.allow_agent()

    app = create(site.visit(), name="Anna Berg", username="Anna")

    assert not app.exception
    assert app.title[0].value == START_TITLE
    assert app.session_state["account"] == {"username": "anna", "name": "Anna Berg"}
    # And it can sign in later, from another browser session.
    assert sign_in(site.visit(), "anna", PASSWORD).title[0].value == START_TITLE


def test_without_the_right_invite_code_no_account_is_created(site):
    app = create(site.visit(), code="a guess")

    assert errors(app) == ["That invite code isn't right."]
    assert site.store.get(accounts.ACCOUNTS, "anna") is None
    assert "account" not in app.session_state


def test_what_is_wrong_with_a_new_account_is_said_plainly(site):
    app = create(site.visit(), password="1234567")

    assert errors(app) == ["Use a password of at least 8 characters."]
    assert site.store.get(accounts.ACCOUNTS, "anna") is None


def test_a_taken_username_is_refused_on_the_page(site):
    accounts.create_account(site.store, "anna", "Anna", PASSWORD)

    app = create(site.visit(), name="Another Anna", password="a different password")

    assert errors(app) == ["That username is taken. Choose another."]
    assert "account" not in app.session_state


# --- a copy without an invite code -----------------------------------------------------------------

def test_without_an_invite_code_the_app_opens_directly(tmp_path):
    runtime = make_runtime(tmp_path, [])
    with patch("agent.config.APP_PASSWORD", ""), \
            patch("ui.runtime.get_runtime", lambda *args, **kwargs: runtime):
        app = AppTest.from_file(APP, default_timeout=30).run()

    assert app.title[0].value == START_TITLE
    assert len(app.tabs) == 0
    runtime.checkpointer.conn.close()


def test_a_new_account_is_copied_to_the_lasting_folder_at_once(site):
    # In the cloud the machine's disk is wiped on a restart. Without this,
    # an account made just before a restart would be gone.
    site.allow_agent()

    with patch("ui.sign_in.backup_memory") as copy_made:
        create(site.visit())

    copy_made.assert_called_once_with()
