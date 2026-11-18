"""The sidebar: conversations, what is remembered, settings and help."""

import streamlit as st

from agent.config import (
    APP_NAME,
    APP_TAGLINE,
    LENGTH_CHOICES,
    MODEL_CHOICES,
    PROFILE_KEYS,
    STYLE_CHOICES,
)
from agent.memory import SETTING_DEFAULTS
from agent.session import Conversation
from ui.assets import brand, fill

# How many conversations are listed before the rest fold away.
RECENT_SHOWN = 5

# What the sidebar can ask the page to do.
NEW = "new"
FORGET = "forget"
GUIDE = "guide"
SIGN_OUT = "sign out"


# Each setting has a widget in the settings panel. The widget's value is
# kept by Streamlit under "set_" plus the setting's name.

def prepare_settings(saved: dict | None = None) -> None:
    """Put the settings in place before the widgets are drawn.

    A setting nobody has touched gets its default. With `saved` (the
    settings of the account that has just signed in), those are put in
    instead.
    """
    for name, default in SETTING_DEFAULTS.items():
        st.session_state.setdefault(f"set_{name}", default)
    for name, value in (saved or {}).items():
        st.session_state[f"set_{name}"] = value


def chosen_settings() -> dict:
    """What the settings panel shows now, by the names used when settings
    are saved (see agent/memory.py)."""
    return {name: st.session_state.get(f"set_{name}", default)
            for name, default in SETTING_DEFAULTS.items()}


def current_settings() -> dict:
    """The settings as the agent needs them. Read at the top of the page,
    before the agent is fetched, so a change takes effect on the same
    click."""
    chosen = chosen_settings()
    return {
        "model_name": chosen["model"],
        "temperature": chosen["temperature"],
        "review_competitors": chosen["review"],
        "answer_style": chosen["style"],
        # The slider shows a word; the agent is given the number behind it.
        "max_answer_tokens": LENGTH_CHOICES.get(chosen["length"]),
    }


def render_sidebar(conversations: list[Conversation], current: str,
                   profile: dict[str, str], waiting: bool,
                   signed_in_as: str | None = None) -> str | None:
    """Show the sidebar. Returns NEW, FORGET, GUIDE or SIGN_OUT if the user
    asked for that, the thread id of a conversation they picked, or None.

    Args:
        profile: What is remembered about the user.
        signed_in_as: The name of the account that is signed in. None when
            the app runs without accounts.
        waiting: True while the agent is stopped for an approval. Settings
            that would change how a paused report continues are locked.
    """
    action = None
    with st.sidebar:
        st.html(brand(APP_NAME))
        st.caption(APP_TAGLINE)

        if signed_in_as:
            with st.container(key="account_panel"):
                # The name was typed by a person: fill() shows it as text.
                st.html(fill("account.html", person=signed_in_as))
                if st.button("Sign out", icon=":material/logout:", key="sign_out",
                             width="stretch"):
                    action = SIGN_OUT

        if st.button("New conversation", icon=":material/add:", width="stretch",
                     key="new_conversation"):
            action = NEW

        st.caption("Conversations")
        if not conversations:
            st.caption("None yet. Ask a question to start one.")
        # The newest few are always visible; the rest fold away so the
        # panels below are not pushed off the screen.
        for conversation in conversations[:RECENT_SHOWN]:
            action = _conversation_button(conversation, current) or action
        older = conversations[RECENT_SHOWN:]
        if older:
            with st.expander(f"{len(older)} older", type="compact"):
                for conversation in older:
                    action = _conversation_button(conversation, current) or action

        action = _memory_panel(profile) or action
        _settings_panel(waiting)
        action = _help_panel() or action
    return action


def _conversation_button(conversation: Conversation, current: str) -> str | None:
    """One conversation in the list. Returns its id if it was picked."""
    is_current = conversation.thread_id == current
    if st.button(conversation.title, key=f"open_{conversation.thread_id}",
                 type="secondary" if is_current else "tertiary",
                 width="stretch") and not is_current:
        return conversation.thread_id
    return None


def _memory_panel(profile: dict[str, str]) -> str | None:
    """What the assistant remembers about the user, with a way to clear it."""
    st.caption("What I remember")
    if not profile:
        st.caption("Nothing yet. Tell me your country, industry or idea and "
                   "I will remember it for next time.")
        return None

    with st.container(key="memory_panel"):
        for key in PROFILE_KEYS:
            if key in profile:
                st.markdown(f":gray[{key.replace('_', ' ').capitalize()}]  \n{profile[key]}")
    if st.button("Forget me", icon=":material/delete:", key="forget_me",
                 help="Deletes everything remembered about you. "
                      "Your conversations are kept."):
        return FORGET
    return None


def _settings_panel(waiting: bool) -> None:
    """Developer settings, kept apart from the everyday experience in a
    closed section. Each widget shows what prepare_settings() put in place,
    and the values are read back with current_settings()."""
    with st.expander("Settings", icon=":material/settings:"):
        models = list(MODEL_CHOICES)
        st.selectbox(
            "Model", models, key="set_model",
            format_func=lambda name: MODEL_CHOICES[name], disabled=waiting,
            help="The language model that answers and researches. All are "
                 "reached through OpenRouter.")
        st.slider(
            "Temperature", 0.0, 1.0, step=0.1, key="set_temperature",
            disabled=waiting,
            help="Lower gives more factual, repeatable answers. Higher gives "
                 "more varied wording. Research works best low.")
        st.select_slider(
            "Maximum answer length", list(LENGTH_CHOICES),
            key="set_length", disabled=waiting,
            help="A hard limit on one chat answer: Short is about 180 words, "
                 "Medium about 450, Long about 900. An answer that reaches it "
                 "is cut off and says so. Reports are never cut. To ask for "
                 "brief wording instead, use the Concise answer style.")
        styles = list(STYLE_CHOICES)
        # The box shows the name only: with its description added, the text
        # was cut off in the narrow sidebar. The help text lists all four,
        # and the line under the box describes the one that is chosen.
        all_styles = "\n\n".join(f"**{name}**: {line}" for name, line in STYLE_CHOICES.items())
        chosen = st.selectbox(
            "Answer style", styles, key="set_style",
            disabled=waiting,
            help="How answers are worded. It never changes the facts, "
                 f"numbers or sources.\n\n{all_styles}")
        st.caption(STYLE_CHOICES[chosen])
        st.toggle(
            "Review competitors before a report",
            key="set_review", disabled=waiting,
            help="When on, a report pauses so you can approve or edit the "
                 "competitor list. Turn it off for a quicker report.")
        if waiting:
            st.caption("Settings are locked while the assistant is waiting "
                       "for your decision.")


def _help_panel() -> str | None:
    with st.expander("Help", icon=":material/help:"):
        st.markdown(
            "**Ask for a report** by naming a product and a country, for "
            "example *healthy meal delivery in Germany*.\n\n"
            "**Ask a single question** about prices, competitors, news, "
            "demand or a company.\n\n"
            "**It will not** give investment advice or invent numbers. What "
            "it cannot find is reported as \"not found\".\n\n"
            "**Reports** can be downloaded, or saved to the reports folder "
            "after you approve."
        )
        if st.button("How it works", icon=":material/travel_explore:", key="help_guide"):
            return GUIDE
    return None
