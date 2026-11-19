"""The language switch: EN | DE at the top right of every screen.

The choice is kept in the browser session under "set_language", the name
the other settings use too, so it is saved with the account like them
(agent/memory.py). The stylesheet keeps the switch in the corner, to the
left of the account badge (see "The language switch").
"""

import streamlit as st

from agent.config import LANGUAGE_CHOICES
from ui.texts import current_language, t


def _chosen() -> None:
    """Take over what was clicked. Clicking the chosen language again
    would switch both off; the language is then left as it was."""
    clicked = st.session_state.get("language_switch")
    if clicked in LANGUAGE_CHOICES:
        st.session_state["set_language"] = clicked


def render_language_switch() -> None:
    # The switch shows the language in use, whatever was clicked last.
    st.session_state["language_switch"] = current_language()
    with st.container(key="language_box"):
        st.segmented_control(
            t("language.label"), list(LANGUAGE_CHOICES), format_func=str.upper,
            key="language_switch", label_visibility="collapsed", help=t("language.help"),
            on_change=_chosen)
