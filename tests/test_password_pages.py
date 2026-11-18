"""Tests for the screens around a password: the "Forgot password?" link
and its email, the page the link opens, and the rows in the sidebar for
changing the password or the email address.

The page is run without a browser, and no email is sent: what would have
been sent is collected in a list.
"""

from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from agent import accounts
from tests.test_mailer import SETTINGS
from tests.test_sign_in import APP, PASSWORD, create, errors, fill, press, sign_in, site  # noqa: F401
from tests.test_two_accounts import two_accounts, visit_as

NEW_PASSWORD = "a brand new password"
LINK_SENT = "If that account has an email address, a link is on its way. It works for 30 minutes."
LINK_DEAD = "This link has expired or was already used. Ask for a new one."


@pytest.fixture
def outbox():
    """Email is set up, and every message that would be sent lands here."""
    sent = []
    with patch.multiple("agent.config", **SETTINGS), \
            patch("agent.mailer.send_later", sent.append):
        yield sent


def labels(app) -> list[str]:
    return [button.label for button in app.button]


def keys(app) -> list[str]:
    return [field.key for field in app.text_input]


def said(app) -> list[str]:
    return [message.value for message in app.success]


def ask_for_link(site, username: str):  # noqa: F811
    app = press(site.visit(), "Forgot password?")
    return press(fill(app, forgot_username=username), "Email me a reset link")


def token_in(message) -> str:
    """The token of the link in a message."""
    body = message.get_content()
    start = body.index("https://markavi.example.com/?reset=") + len("https://markavi.example.com/?reset=")
    return body[start:].split()[0]


def open_link(token: str):
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["reset"] = token
    return app.run()


def choose_new(app, new: str, again: str | None = None):
    return press(fill(app, reset_new=new, reset_again=new if again is None else again),
                 "Save new password")


# --- asking for a link ---------------------------------------------------------------------------

def test_without_email_set_up_there_is_no_forgot_password_link(site):  # noqa: F811
    assert "Forgot password?" not in labels(site.visit())


def test_asking_for_a_link_sends_one_to_the_accounts_address(site, outbox):  # noqa: F811
    accounts.create_account(site.store, "anna", "Anna", PASSWORD, email="anna@example.com")

    app = ask_for_link(site, "anna")

    assert not app.exception
    assert said(app) == [LINK_SENT]
    [message] = outbox
    assert message["To"] == "anna@example.com"
    assert "https://markavi.example.com/?reset=" in message.get_content()


def test_an_unknown_username_gets_the_same_answer_and_no_email(site, outbox):  # noqa: F811
    app = ask_for_link(site, "nobody")

    assert said(app) == [LINK_SENT]
    assert outbox == []


def test_back_to_sign_in_returns_to_the_two_tabs(site, outbox):  # noqa: F811
    app = press(site.visit(), "Forgot password?")
    assert len(app.tabs) == 0

    press(app, "Back to sign in")

    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]


# --- the page the link opens ------------------------------------------------------------------------

@pytest.fixture
def link(site, outbox):  # noqa: F811
    """The token of a link that was just emailed to anna."""
    accounts.create_account(site.store, "anna", "Anna", PASSWORD, email="anna@example.com")
    ask_for_link(site, "anna")
    return token_in(outbox[0])


def test_the_link_opens_a_page_to_choose_a_new_password(site, link):  # noqa: F811
    app = open_link(link)

    assert not app.exception
    assert "reset_new" in keys(app) and "reset_again" in keys(app)
    assert any("anna" in caption.value for caption in app.caption)
    assert len(app.tabs) == 0                          # not the sign-in tabs
    assert len(app.chat_input) == 0                    # and not the app


def test_saving_sets_the_new_password_and_returns_to_sign_in(site, link):  # noqa: F811
    with patch("ui.sign_in.backup_memory") as copy_made:
        app = choose_new(open_link(link), NEW_PASSWORD)

    assert not app.exception
    assert said(app) == ["Password changed. Sign in with your new password."]
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]
    assert accounts.sign_in(site.store, "anna", NEW_PASSWORD).username == "anna"
    with pytest.raises(accounts.AccountError):
        accounts.sign_in(site.store, "anna", PASSWORD)
    copy_made.assert_called_once_with()                # kept across a restart in the cloud


def test_two_different_entries_are_refused(site, link):  # noqa: F811
    app = choose_new(open_link(link), NEW_PASSWORD, again="a brand new passwort")

    assert errors(app) == ["The two new passwords are not the same."]
    assert accounts.sign_in(site.store, "anna", PASSWORD).username == "anna"      # unchanged


def test_a_used_link_says_so_and_shows_no_form(site, link):  # noqa: F811
    choose_new(open_link(link), NEW_PASSWORD)

    app = open_link(link)

    assert errors(app) == [LINK_DEAD]
    assert "reset_new" not in keys(app)
    assert "Back to sign in" in labels(app)


def test_a_made_up_link_says_the_same(site, outbox):  # noqa: F811
    app = open_link("a-made-up-token")

    assert errors(app) == [LINK_DEAD]
    assert "reset_new" not in keys(app)


# --- the email address of a new account --------------------------------------------------------------

def test_a_new_account_needs_an_email_address(site):  # noqa: F811
    app = create(site.visit(), email="")

    assert errors(app) == ["Enter a valid email address."]
    assert site.store.get(accounts.ACCOUNTS, "anna") is None


def test_a_new_accounts_email_address_is_kept(site):  # noqa: F811
    site.allow_agent()

    create(site.visit(), email="Anna@Example.com")

    assert accounts.email_of(site.store, "anna") == "anna@example.com"


# --- the rows in the sidebar ---------------------------------------------------------------------------

def test_the_password_is_changed_from_the_sidebar(site):  # noqa: F811
    two_accounts(site)
    app = visit_as(site, "anna")

    with patch("ui.account_panel.backup_memory") as copy_made:
        press(fill(app, cp_current=PASSWORD, cp_new=NEW_PASSWORD, cp_again=NEW_PASSWORD),
              "Change password")

    assert not app.exception
    assert "Password changed." in said(app)
    assert accounts.sign_in(site.store, "anna", NEW_PASSWORD).username == "anna"
    assert app.session_state["account"]["username"] == "anna"        # still signed in
    copy_made.assert_called_once_with()


def test_a_wrong_current_password_changes_nothing(site):  # noqa: F811
    two_accounts(site)
    app = visit_as(site, "anna")

    press(fill(app, cp_current="not the password", cp_new=NEW_PASSWORD, cp_again=NEW_PASSWORD),
          "Change password")

    assert errors(app) == ["That is not your current password."]
    assert accounts.sign_in(site.store, "anna", PASSWORD).username == "anna"


def test_two_different_new_passwords_change_nothing(site):  # noqa: F811
    two_accounts(site)
    app = visit_as(site, "anna")

    press(fill(app, cp_current=PASSWORD, cp_new=NEW_PASSWORD, cp_again="something else here"),
          "Change password")

    assert errors(app) == ["The two new passwords are not the same."]
    assert accounts.sign_in(site.store, "anna", PASSWORD).username == "anna"


def test_the_sidebar_shows_the_email_address_on_file(site):  # noqa: F811
    two_accounts(site)

    anna, ben = visit_as(site, "anna"), visit_as(site, "ben")

    assert any("anna@example.com" in caption.value for caption in anna.sidebar.caption)
    assert any("No email address yet" in caption.value for caption in ben.sidebar.caption)


def test_the_email_address_is_set_from_the_sidebar_with_the_password(site):  # noqa: F811
    two_accounts(site)
    app = visit_as(site, "ben")

    press(fill(app, em_email="ben@example.com", em_password="not the password"), "Save email")
    assert errors(app) == ["That is not your current password."]
    assert accounts.email_of(site.store, "ben") == ""

    press(fill(app, em_email="Ben@Example.com", em_password=PASSWORD), "Save email")
    assert "Email address saved." in said(app)
    assert accounts.email_of(site.store, "ben") == "ben@example.com"


def test_without_accounts_the_sidebar_has_no_password_or_email_rows(page):
    app = page()

    assert "cp_current" not in keys(app) and "em_email" not in keys(app)


from tests.test_app import page  # noqa: E402,F401  (a fixture)
