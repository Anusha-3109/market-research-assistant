"""The email with a link for a forgotten password.

Email is sent through an ordinary mail account (by default Gmail, with an
"app password") using Python's own mail library. Three settings switch it
on; without them the app offers no "Forgot password?" link:

    SMTP_USER      the address the email is sent from
    SMTP_PASSWORD  the app password of that mail account
    APP_URL        the public address of the app, for the link

The message is plain text. Nothing a person typed (their name) can become
markup or an extra header.
"""

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage

from agent import config
from agent.config import APP_NAME

log = logging.getLogger(__name__)


def mail_is_set_up() -> bool:
    return bool(config.SMTP_USER and config.SMTP_PASSWORD and config.APP_URL)


def reset_link(token: str) -> str:
    """The address that opens the "Choose a new password" page."""
    return f"{config.APP_URL.rstrip('/')}/?reset={token}"


def reset_email(name: str, username: str, to: str, link: str) -> EmailMessage:
    """The message that carries the link."""
    message = EmailMessage()
    message["From"] = f"{APP_NAME} <{config.SMTP_USER}>"
    message["To"] = to
    message["Subject"] = f"Reset your {APP_NAME} password"
    message.set_content(
        f"Hello {name},\n\n"
        f"Someone asked to reset the password of your {APP_NAME} account {username}.\n\n"
        f"Choose a new password here:\n{link}\n\n"
        "The link works once, for 30 minutes.\n\n"
        "If you did not ask for this, ignore this email: your password stays as it is.\n")
    return message


def send(message: EmailMessage) -> None:
    """Send a message. The connection is encrypted before the password is
    given."""
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(message)


def send_quietly(message: EmailMessage) -> bool:
    """Send a message and report whether it worked. A failure is logged,
    never raised: the page must say the same thing either way."""
    try:
        send(message)
    except (OSError, smtplib.SMTPException) as problem:
        # Only the kind of problem is logged, never the message or a password.
        log.error("An email could not be sent: %s", type(problem).__name__)
        return False
    return True


def send_later(message: EmailMessage) -> None:
    """Send a message without making the page wait. The page then answers
    equally fast whether or not an email goes out, so the time it takes
    does not reveal which accounts exist."""
    threading.Thread(target=send_quietly, args=(message,), daemon=True).start()
