"""The sidebar: conversations, what is remembered, settings and help."""

import streamlit as st

from agent.config import (
    APP_NAME,
    LENGTH_CHOICES,
    MODEL_CHOICES,
    PROFILE_KEYS,
    STYLE_CHOICES,
)
from agent.memory import SETTING_DEFAULTS
from agent.session import Conversation
from ui.assets import brand
from ui.texts import current_language, t

# How many conversations are listed before the rest fold away.
RECENT_SHOWN = 5

# What the sidebar can ask the page to do.
NEW = "new"
FORGET = "forget"
GUIDE = "guide"


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
        "language": chosen["language"],
        # The slider shows a word; the agent is given the number behind it.
        "max_answer_tokens": LENGTH_CHOICES.get(chosen["length"]),
    }


# The views of an open conversation, in the order of their links.
SNAPSHOT, ASK, REPORT = "snapshot", "ask", "report"
VIEW_ICONS = {SNAPSHOT: ":material/dashboard:", ASK: ":material/chat_bubble:",
              REPORT: ":material/description:"}


def current_view(thread_id: str, views: list[str], default: str = ASK) -> str:
    """The view of this conversation that is open: the one chosen with a
    link in the sidebar, for this conversation only, or else `default`."""
    chosen = st.session_state.get("view")
    if chosen and chosen["thread"] == thread_id and chosen["name"] in views:
        return chosen["name"]
    return default if default in views else ASK


def _choose_view(thread_id: str, name: str) -> None:
    st.session_state["view"] = {"thread": thread_id, "name": name}


def _note_picked() -> None:
    """Runs when the conversation picker is changed, before the page is
    drawn again: keeps what was picked."""
    st.session_state["picked_conversation"] = st.session_state["pick_conversation"]


def picker_entries(conversations: list[Conversation], current: str, title: str) -> dict[str, str]:
    """What the conversation picker lists: the id of each conversation and
    the text of its entry, with the open conversation first.

    Every entry reads differently. The browser tells the picker which
    entry is chosen by its text, so two conversations with the same title
    were mixed up: any click in one of them jumped to the other. A repeated
    title gets a number: "Oat milk in Germany (2)".
    """
    titles = {conversation.thread_id: conversation.title for conversation in conversations}
    titles.setdefault(current, title)        # an older one that is not in the recent list
    entries: dict[str, str] = {}
    for thread_id in [current] + [other for other in titles if other != current]:
        entry, copy = titles[thread_id], 2
        while entry in entries.values():
            entry, copy = f"{titles[thread_id]} ({copy})", copy + 1
        entries[thread_id] = entry
    return entries


def _conversation_picker(conversations: list[Conversation], current: str, title: str) -> str | None:
    """The conversations in one box, with the open one chosen. Returns the
    id of another one if it was just picked."""
    entries = picker_entries(conversations, current, title)
    # The box always shows the conversation that is open. Without this line
    # it would keep showing one picked earlier after "New conversation".
    st.session_state["pick_conversation"] = current
    # The word above the box is written as a line of its own. As the box's
    # own label it stayed in the old language in the browser after the
    # language was switched.
    st.caption(t("sidebar.conversation"))
    st.selectbox(t("sidebar.conversation"), list(entries), key="pick_conversation",
                 format_func=entries.get, on_change=_note_picked, width="stretch",
                 label_visibility="collapsed")
    picked = st.session_state.pop("picked_conversation", None)
    return picked if picked and picked != current else None


def render_sidebar(conversations: list[Conversation], current: str,
                   profile: dict[str, str], waiting: bool,
                   title: str = "", views: list[str] | None = None,
                   shown_view: str | None = None) -> str | None:
    """Show the sidebar. Returns NEW, FORGET or GUIDE if the user asked for
    that, the thread id of a conversation they picked, or None.

    On the front page the conversations are listed one under the other.
    Inside an open conversation the list gives way to a picker, followed by
    the links to the views of that conversation.

    Args:
        title: The title of the open conversation; "" on the front page.
        views: The views the open conversation has, such as [ASK, REPORT].
        shown_view: The one of them that is open.
        profile: What is remembered about the user.
        waiting: True while the agent is stopped for an approval. Settings
            that would change how a paused report continues are locked.
    """
    action = None
    with st.sidebar:
        # The sidebar has three parts. The head (logo and name) and the
        # foot never move. The part between them holds the conversations
        # and scrolls when they do not fit. The stylesheet does this (see
        # "The three parts of the sidebar").
        with st.container(key="sidebar_head"):
            st.html(brand(APP_NAME))
            st.caption(t("sidebar.tagline"))

        with st.container(key="sidebar_top"):
            if st.button(t("sidebar.new_conversation"), icon=":material/add:", width="stretch",
                         key="new_conversation"):
                action = NEW

            if views:
                action = _conversation_picker(conversations, current, title) or action
                shown = shown_view or current_view(current, views)
                with st.container(key="view_links"):
                    for name in views:
                        st.button(t(f"view.{name}"), key=f"view_{name}", icon=VIEW_ICONS[name],
                                  type="secondary" if name == shown else "tertiary",
                                  width="stretch", on_click=_choose_view, args=(current, name))
            else:
                st.caption(t("sidebar.conversations"))
                if not conversations:
                    st.caption(t("sidebar.none_yet"))
                # The newest few are always visible; the rest fold away so
                # the panels below are not pushed off the screen.
                for conversation in conversations[:RECENT_SHOWN]:
                    action = _conversation_button(conversation, current) or action
                older = conversations[RECENT_SHOWN:]
                if older:
                    with st.expander(t("sidebar.older", count=len(older)), type="compact"):
                        for conversation in older:
                            action = _conversation_button(conversation, current) or action

            action = _memory_panel(profile) or action

        # The foot: two plain rows.
        with st.container(key="sidebar_foot"):
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
    st.caption(t("memory.title"))
    if not profile:
        st.caption(t("memory.nothing"))
        return None

    with st.container(key="memory_panel"):
        for key in PROFILE_KEYS:
            if key in profile:
                st.markdown(f":gray[{t(f'profile.{key}')}]  \n{profile[key]}")
    if st.button(t("memory.forget"), icon=":material/delete:", key="forget_me",
                 help=t("memory.forget_help")):
        return FORGET
    return None


def _settings_panel(waiting: bool) -> None:
    """Developer settings, kept apart from the everyday experience in a
    closed section. Each widget shows what prepare_settings() put in place,
    and the values are read back with current_settings()."""
    # A choice is shown by its name in the chosen language. What is kept,
    # saved and given to the agent is the choice itself ("Concise"), which
    # is the same in every language.
    # (The language is read once here: the functions that name a choice
    # are also called after the page is drawn, when it can no longer be asked.)
    language = current_language()
    with st.expander(t("settings.title"), icon=":material/settings:"):
        models = list(MODEL_CHOICES)
        st.selectbox(
            t("settings.model"), models, key="set_model",
            format_func=lambda name: MODEL_CHOICES[name], disabled=waiting,
            help=t("settings.model_help"))
        st.slider(
            t("settings.temperature"), 0.0, 1.0, step=0.1, key="set_temperature",
            disabled=waiting, help=t("settings.temperature_help"))
        st.select_slider(
            t("settings.length"), list(LENGTH_CHOICES),
            format_func=lambda name: t(f"length.{name}", language=language),
            key="set_length", disabled=waiting, help=t("settings.length_help"))
        styles = list(STYLE_CHOICES)
        # The box shows the name only: with its description added, the text
        # was cut off in the narrow sidebar. The help text lists all four,
        # and the line under the box describes the one that is chosen.
        all_styles = "\n\n".join(f"**{t(f'style.{name}')}**: {t(f'style.about.{name}')}"
                                 for name in styles)
        chosen = st.selectbox(
            t("settings.style"), styles, key="set_style",
            format_func=lambda name: t(f"style.{name}", language=language), disabled=waiting,
            help=f"{t('settings.style_help')}\n\n{all_styles}")
        st.caption(t(f"style.about.{chosen}"))
        st.toggle(
            t("settings.review"), key="set_review", disabled=waiting,
            help=t("settings.review_help"))
        if waiting:
            st.caption(t("settings.locked"))


def _help_panel() -> str | None:
    with st.expander(t("help.title"), icon=":material/help:"):
        st.markdown(t("help.body"))
        if st.button(t("help.how"), icon=":material/travel_explore:", key="help_guide"):
            return GUIDE
    return None
