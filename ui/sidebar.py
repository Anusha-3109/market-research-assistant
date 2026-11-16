"""The sidebar: start a new conversation or reopen an earlier one."""

import streamlit as st

from agent.config import APP_NAME, APP_TAGLINE
from agent.session import Conversation


def render_sidebar(conversations: list[Conversation], current: str) -> str | None:
    """Show the sidebar. Returns "new" if the user asked for a new
    conversation, the thread id of a conversation they picked, or None."""
    action = None
    with st.sidebar:
        st.subheader(APP_NAME, anchor=False)
        st.caption(APP_TAGLINE)

        if st.button("New conversation", icon=":material/add:", width="stretch",
                     key="new_conversation"):
            action = "new"

        st.caption("Conversations")
        if not conversations:
            st.caption("None yet. Ask a question to start one.")
        for conversation in conversations:
            is_current = conversation.thread_id == current
            if st.button(conversation.title, key=f"open_{conversation.thread_id}",
                         type="secondary" if is_current else "tertiary",
                         width="stretch") and not is_current:
                action = conversation.thread_id
    return action
