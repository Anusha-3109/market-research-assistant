"""Settings shared by all tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_local_password():
    """The tests must not depend on what is in the developer's own .env
    file. If APP_PASSWORD is set there, the page would show the password
    screen and every page test would fail. Tests about the password set
    their own."""
    with patch("agent.config.APP_PASSWORD", ""):
        yield
