"""The app's own words in the chosen language.

    t("account.sign_out")        ->  "Sign out" or "Abmelden"

The words are kept in ui/words, one list per language. The language is the
one chosen with the switch at the top right (ui/language.py).
"""

import streamlit as st

from agent.config import LANGUAGE, LANGUAGE_CHOICES
from ui.words import de, en

TEXTS = {"en": en.TEXTS, "de": de.TEXTS}


def current_language() -> str:
    """The language chosen in this browser session, or English."""
    chosen = st.session_state.get("set_language")
    return chosen if chosen in LANGUAGE_CHOICES else LANGUAGE


def t(key: str, language: str | None = None, **values) -> str:
    """The text with this name, with its blanks filled in.

    A name that does not exist raises KeyError: that is a mistake in the
    code, and should not reach a visitor as an empty label.
    """
    language = language or current_language()
    english = TEXTS[LANGUAGE][key]
    text = TEXTS.get(language, {}).get(key, english)
    return text.format(**values) if values else text


def counted(key: str, count: int, language: str | None = None) -> str:
    """A text that names a number of things: "of 1 candidate" or "of 5
    candidates". Such a text has two forms, kept under the names
    key + "_one" and key + "_many"."""
    return t(f"{key}_one" if count == 1 else f"{key}_many", language=language, count=count)
