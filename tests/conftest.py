"""Settings shared by all tests."""

import os

# No test may send a trace to LangSmith, whatever the developer's own .env
# says. This line runs before any test file is imported, so it is in place
# before agent.config reads the settings (agent/tracing.py).
os.environ["LANGSMITH_TRACING"] = "false"

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_exchange_rates():
    """No test may use the internet. A report's figures would otherwise be
    converted with a real exchange rate. Tests about conversion pass a
    rate of their own (test_currency.py)."""
    with patch("agent.currency.real_rate", lambda source, target: None):
        yield


@pytest.fixture(autouse=True)
def no_local_settings():
    """The tests must not depend on what is in the developer's own .env
    file. If APP_PASSWORD is set there, the page would show the sign-in
    screen and every page test would fail; with the email settings, a test
    could try to send real email. Tests about these set their own."""
    with patch.multiple("agent.config", APP_PASSWORD="", SMTP_USER="", SMTP_PASSWORD="",
                        APP_URL="", SMTP_HOST="smtp.gmail.com", SMTP_PORT=587):
        yield
