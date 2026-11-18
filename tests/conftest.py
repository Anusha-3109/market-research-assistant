"""Settings shared by all tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_local_settings():
    """The tests must not depend on what is in the developer's own .env
    file. If APP_PASSWORD is set there, the page would show the sign-in
    screen and every page test would fail; with the email settings, a test
    could try to send real email. Tests about these set their own."""
    with patch.multiple("agent.config", APP_PASSWORD="", SMTP_USER="", SMTP_PASSWORD="",
                        APP_URL="", SMTP_HOST="smtp.gmail.com", SMTP_PORT=587):
        yield
