"""The sidebar of a page other than Research: the logo and the page links at
the top, and Help with the account badge at the bottom.

The bottom part is the same as on the Research sidebar (ui/sidebar.py) and
the stylesheet keeps it at the bottom on every page.
"""

import streamlit as st

from agent.config import APP_NAME
from ui.account_badge import render_account_badge
from ui.assets import brand
from ui.pages import render_page_links
from ui.texts import t
from agent.tracing import tracing_is_on


def render_page_sidebar(page: str, account) -> None:
    with st.sidebar:
        with st.container(key="sidebar_head"):
            st.html(brand(APP_NAME))
            st.caption(t("sidebar.tagline"))
            render_page_links(page, account)
        with st.container(key="sidebar_foot"):
            with st.expander(t("help.title"), icon=":material/help:"):
                st.markdown(t("help.body"))
                st.caption(t("help.tracing_on") if tracing_is_on() else t("help.tracing_off"))
            if account is not None:
                render_account_badge(account)
