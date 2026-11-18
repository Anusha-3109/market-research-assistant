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


# --- changing the password or the email address, from the sign-in page ----------------------------

NO_MATCH = "That username and password don't match. Try again."


def test_the_sign_in_page_offers_both_changes_even_without_email_set_up(site):  # noqa: F811
    offered = labels(site.visit())

    assert "Change password" in offered and "Change email" in offered
    assert "Forgot password?" not in offered


def change_password(app, username="anna", current=PASSWORD, new=NEW_PASSWORD, again=None):
    press(app, "Change password")
    fill(app, cp_username=username, cp_current=current, cp_new=new,
         cp_again=new if again is None else again)
    return press(app, "Save new password")


def change_email(app, username="ben", password=PASSWORD, email="ben@example.com"):
    press(app, "Change email")
    fill(app, em_username=username, em_password=password, em_email=email)
    return press(app, "Save email")


def test_the_password_is_changed_from_the_sign_in_page(site):  # noqa: F811
    two_accounts(site)

    with patch("ui.sign_in.backup_memory") as copy_made:
        app = change_password(site.visit())

    assert not app.exception
    assert said(app) == ["Password changed. Sign in with your new password."]
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]
    assert accounts.sign_in(site.store, "anna", NEW_PASSWORD).username == "anna"
    assert "account" not in app.session_state          # changing it does not sign you in
    copy_made.assert_called_once_with()


def test_a_wrong_current_password_changes_nothing(site):  # noqa: F811
    two_accounts(site)

    app = change_password(site.visit(), current="not the password")

    assert errors(app) == [NO_MATCH]
    assert accounts.sign_in(site.store, "anna", PASSWORD).username == "anna"


def test_an_unknown_username_gets_the_same_message_as_a_wrong_password(site):  # noqa: F811
    two_accounts(site)

    assert errors(change_password(site.visit(), username="nobody")) == [NO_MATCH]
    assert errors(change_email(site.visit(), username="nobody")) == [NO_MATCH]


def test_two_different_new_passwords_change_nothing(site):  # noqa: F811
    two_accounts(site)

    app = change_password(site.visit(), again="something else here")

    assert errors(app) == ["The two new passwords are not the same."]
    assert accounts.sign_in(site.store, "anna", PASSWORD).username == "anna"


def test_the_email_address_is_set_from_the_sign_in_page_with_the_password(site):  # noqa: F811
    two_accounts(site)

    refused = change_email(site.visit(), password="not the password")
    assert errors(refused) == [NO_MATCH]
    assert accounts.email_of(site.store, "ben") == ""

    with patch("ui.sign_in.backup_memory") as copy_made:
        app = change_email(site.visit(), email="Ben@Example.com")

    assert said(app) == ["Email address saved: ben@example.com"]
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]
    assert accounts.email_of(site.store, "ben") == "ben@example.com"
    copy_made.assert_called_once_with()


def test_something_that_is_not_an_address_is_refused_on_the_page(site):  # noqa: F811
    two_accounts(site)

    app = change_email(site.visit(), email="not an address")

    assert errors(app) == ["Enter a valid email address."]


@pytest.mark.parametrize("link_label", ["Change password", "Change email"])
def test_back_to_sign_in_leaves_either_form(site, link_label):  # noqa: F811
    app = press(site.visit(), link_label)
    assert len(app.tabs) == 0

    press(app, "Back to sign in")

    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]


def test_once_signed_in_the_sidebar_has_no_password_or_email_rows(site):  # noqa: F811
    two_accounts(site)

    app = visit_as(site, "anna")

    assert "cp_current" not in keys(app) and "em_email" not in keys(app)
    assert "Change password" not in labels(app) and "Change email" not in labels(app)


