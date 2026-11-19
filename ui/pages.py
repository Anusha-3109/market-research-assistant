"""The pages of the app and the links to them at the top of the sidebar.

Research is the app itself: the start screen and the conversations. The
other pages (Dashboard, How it works, Admin) are opened with a link and
drawn in place of it. Which page is open lives in the browser session.
"""

import streamlit as st

from agent import config
from ui.texts import t

RESEARCH, DASHBOARD, HOW, ADMIN = "research", "dashboard", "how", "admin"
PAGES = [RESEARCH, DASHBOARD, HOW, ADMIN]
ICONS = {RESEARCH: ":material/chat_bubble:", DASHBOARD: ":material/bar_chart:",
         HOW: ":material/travel_explore:", ADMIN: ":material/shield_person:"}


def is_admin(account) -> bool:
    """On your own computer (no accounts) you are the admin. On a deployed
    copy, the accounts named in ADMIN_USERNAMES are."""
    if account is None:
        return True
    return account.username in config.ADMIN_USERNAMES


def current_page(account) -> str:
    page = st.session_state.get("page", RESEARCH)
    if page == ADMIN and not is_admin(account):
        return RESEARCH
    return page if page in PAGES else RESEARCH


def _open(page: str) -> None:
    st.session_state["page"] = page


def render_page_links(open_page: str, account) -> None:
    """One link per page; the open one is marked."""
    with st.container(key="page_links"):
        for page in PAGES:
            if page == ADMIN and not is_admin(account):
                continue
            st.button(t(f"page.{page}"), key=f"page_{page}", icon=ICONS[page],
                      type="secondary" if page == open_page else "tertiary", width="stretch",
                      on_click=_open, args=(page,))
