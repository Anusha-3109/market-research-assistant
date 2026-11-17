"""Tests for the two settings a deployed copy uses: where data is stored,
and the password screen."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from agent import config
from tests.test_app import make_runtime
from ui.password import password_matches

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PASSWORD = "open sesame"


# --- where data is stored -------------------------------------------------------------------

def test_without_a_data_folder_everything_stays_in_the_project():
    reports, memory = config.storage_paths("")

    assert reports == config.PROJECT_DIR / "reports"
    assert memory == config.PROJECT_DIR / "data" / "memory.db"


def test_with_a_data_folder_reports_and_memory_go_there():
    reports, memory = config.storage_paths("/mnt/markavi")

    assert reports == Path("/mnt/markavi/reports")
    assert memory == Path("/mnt/markavi/memory.db")


def test_a_data_folder_of_only_spaces_counts_as_not_set():
    assert config.storage_paths("   ") == config.storage_paths("")


# --- the password ------------------------------------------------------------------------------

def test_only_the_exact_password_matches():
    assert password_matches(PASSWORD, PASSWORD)
    assert not password_matches("Open sesame", PASSWORD)
    assert not password_matches("", PASSWORD)


def no_agent(*args, **kwargs):
    raise AssertionError("the agent was created before the password was given")


def test_with_a_password_set_only_the_form_is_shown():
    with patch("agent.config.APP_PASSWORD", PASSWORD), \
            patch("ui.runtime.get_runtime", no_agent):
        app = AppTest.from_file(APP, default_timeout=30).run()

    assert not app.exception
    assert app.text_input[0].label == "Password"
    assert len(app.chat_input) == 0                       # no question box yet
    assert not [b for b in app.button if (b.key or "").startswith("card_")]


def test_a_wrong_password_is_refused():
    with patch("agent.config.APP_PASSWORD", PASSWORD), \
            patch("ui.runtime.get_runtime", no_agent):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.text_input[0].set_value("guess")
        app.button[0].click().run()

    assert not app.exception
    assert app.error[0].value == "That is not the right password."
    assert len(app.chat_input) == 0
    assert "signed_in" not in app.session_state


def test_the_right_password_opens_the_app():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        runtime = make_runtime(Path(folder), [])
        with patch("agent.config.APP_PASSWORD", PASSWORD), \
                patch("ui.runtime.get_runtime", lambda *args, **kwargs: runtime):
            app = AppTest.from_file(APP, default_timeout=30).run()
            app.text_input[0].set_value(PASSWORD)
            app.button[0].click().run()

        assert not app.exception
        assert app.session_state["signed_in"] is True
        assert app.title[0].value == "Research **any market**."
        runtime.checkpointer.conn.close()


def test_without_a_password_the_app_opens_directly():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        runtime = make_runtime(Path(folder), [])
        with patch("agent.config.APP_PASSWORD", ""), \
                patch("ui.runtime.get_runtime", lambda *args, **kwargs: runtime):
            app = AppTest.from_file(APP, default_timeout=30).run()

        assert app.title[0].value == "Research **any market**."
        runtime.checkpointer.conn.close()
