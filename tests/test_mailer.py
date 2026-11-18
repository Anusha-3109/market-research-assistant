"""Tests for the email with a link for a forgotten password.

No email is sent: the mail server is replaced by a fake that records what
it was asked to do.
"""

from unittest.mock import patch

import pytest

from agent import mailer

SETTINGS = {"SMTP_USER": "markavi.sender@example.com", "SMTP_PASSWORD": "an-app-password",
            "APP_URL": "https://markavi.example.com/"}


@pytest.fixture
def mail_settings():
    """The settings a deployed copy has."""
    with patch.multiple("agent.config", **SETTINGS):
        yield


class FakeServer:
    """Stands in for the mail server and records each step."""

    steps: list = []

    def __init__(self, host, port, timeout=None):
        FakeServer.steps = [("connect", host, port)]

    def __enter__(self):
        return self

    def __exit__(self, *problem):
        FakeServer.steps.append(("quit",))

    def starttls(self, context=None):
        FakeServer.steps.append(("starttls", context is not None))

    def login(self, user, password):
        FakeServer.steps.append(("login", user, password))

    def send_message(self, message):
        FakeServer.steps.append(("send", message["To"]))


# --- whether email can be sent ---------------------------------------------------------------

def test_without_settings_no_email_can_be_sent():
    assert mailer.mail_is_set_up() is False


def test_with_all_three_settings_email_can_be_sent(mail_settings):
    assert mailer.mail_is_set_up() is True


@pytest.mark.parametrize("missing", ["SMTP_USER", "SMTP_PASSWORD", "APP_URL"])
def test_one_missing_setting_is_enough_to_switch_it_off(missing):
    with patch.multiple("agent.config", **{**SETTINGS, missing: ""}):
        assert mailer.mail_is_set_up() is False


# --- the link and the message --------------------------------------------------------------------

def test_the_link_points_at_the_apps_own_address(mail_settings):
    assert mailer.reset_link("abc123") == "https://markavi.example.com/?reset=abc123"


def test_the_message_goes_to_the_account_holder_with_the_link(mail_settings):
    message = mailer.reset_email("Anna Berg", "anna", "anna@example.com",
                                 "https://markavi.example.com/?reset=abc123")

    assert message["To"] == "anna@example.com"
    assert message["From"] == "Markavi <markavi.sender@example.com>"
    assert message["Subject"] == "Reset your Markavi password"
    body = message.get_content()
    assert "Hello Anna Berg," in body
    assert "account anna" in body
    assert "https://markavi.example.com/?reset=abc123" in body
    assert "30 minutes" in body
    assert "If you did not ask for this, ignore this email" in body


def test_the_message_is_plain_text(mail_settings):
    message = mailer.reset_email("<b>Anna</b>", "anna", "anna@example.com", "https://x.example/?reset=t")

    assert message.get_content_type() == "text/plain"
    assert "<b>Anna</b>" in message.get_content()        # shown as typed, never run as markup


# --- sending -----------------------------------------------------------------------------------

def test_sending_encrypts_the_connection_before_logging_in(mail_settings):
    message = mailer.reset_email("Anna", "anna", "anna@example.com", "https://x.example/?reset=t")

    with patch("smtplib.SMTP", FakeServer):
        mailer.send(message)

    assert FakeServer.steps == [
        ("connect", "smtp.gmail.com", 587),
        ("starttls", True),
        ("login", "markavi.sender@example.com", "an-app-password"),
        ("send", "anna@example.com"),
        ("quit",),
    ]


def test_a_mail_server_that_fails_does_not_break_the_page(mail_settings, caplog):
    def refuse(*args, **kwargs):
        raise OSError("the mail server is unreachable")

    message = mailer.reset_email("Anna", "anna", "anna@example.com", "https://x.example/?reset=t")

    with patch("smtplib.SMTP", refuse):
        assert mailer.send_quietly(message) is False

    assert "could not be sent" in caplog.text
    assert "an-app-password" not in caplog.text


def test_a_message_that_was_sent_reports_success(mail_settings):
    message = mailer.reset_email("Anna", "anna", "anna@example.com", "https://x.example/?reset=t")

    with patch("smtplib.SMTP", FakeServer):
        assert mailer.send_quietly(message) is True
