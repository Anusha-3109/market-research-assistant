"""The sidebar of a page other than Research: the logo, the page links and
the help panel."""

import streamlit as st

from agent.config import APP_NAME
from ui.assets import brand
from ui.pages import render_page_links
from ui.texts import t


def render_page_sidebar(page: str, account) -> None:
    with st.sidebar:
        with st.container(key="sidebar_head"):
            st.html(brand(APP_NAME))
            st.caption(t("sidebar.tagline"))
            render_page_links(page, account)
