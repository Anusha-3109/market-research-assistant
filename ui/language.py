"""The language switch: EN | DE at the top right of every screen.

The choice is kept in the browser session under "set_language", the name
the other settings use too, so it is saved with the account like them
(agent/memory.py). The stylesheet keeps the switch in the corner, to the
left of the account badge (see "The language switch").
"""

import streamlit as st

from agent.config import LANGUAGE_CHOICES, THEME, THEME_CHOICES
from ui.texts import current_language, t


def _chosen() -> None:
    """Take over what was clicked. Clicking the chosen language again
    would switch both off; the language is then left as it was."""
    clicked = st.session_state.get("language_switch")
    if clicked in LANGUAGE_CHOICES:
        st.session_state["set_language"] = clicked


def _theme_chosen() -> None:
    clicked = st.session_state.get("theme_switch")
    if clicked in THEME_CHOICES:
        st.session_state["set_theme"] = clicked


def current_theme() -> str:
    chosen = st.session_state.get("set_theme")
    return chosen if chosen in THEME_CHOICES else THEME


# Dark: the page's colours are turned around, then turned back for pictures
# (the logo, the robot, site icons, charts' images), so those keep their
# own colours. Streamlit cannot change its own theme while it runs.
DARK = """<style class="gw-dark">
.stApp { filter: invert(0.9) hue-rotate(180deg); background: #ffffff; }
.stApp img, .stApp video, .gw-logo, .gw-avatar, .gw-src-icon,
.st-key-assistant_launcher button, [data-testid="stChatMessageAvatarCustom"] {
    filter: invert(1) hue-rotate(180deg);
}
</style>"""


def render_language_switch() -> None:
    """EN | DE and Light | Dark, side by side at the top right."""
    # Each switch shows what is in use, whatever was clicked last.
    st.session_state["language_switch"] = current_language()
    st.session_state["theme_switch"] = current_theme()
    with st.container(key="language_box", horizontal=True, gap="small"):
        st.segmented_control(
            t("language.label"), list(LANGUAGE_CHOICES), format_func=str.upper,
            key="language_switch", label_visibility="collapsed", help=t("language.help"),
            on_change=_chosen)
        st.segmented_control(
            t("theme.label"), list(THEME_CHOICES),
            format_func=lambda name: t(f"theme.{name}"),
            key="theme_switch", label_visibility="collapsed", on_change=_theme_chosen)
    if current_theme() == "dark":
        st.html(DARK)
