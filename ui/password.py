"""The password screen of a deployed copy.

On your own computer no password is set and the app opens directly. A copy
running in the cloud sets APP_PASSWORD; a visitor must then enter it once
per browser session before anything else is shown or any API key is used.
"""

import hmac

import streamlit as st

from agent import config
from agent.config import APP_NAME, APP_TAGLINE
from ui.assets import brand


def password_matches(typed: str, expected: str) -> bool:
    """Compare in a way that takes the same time whether the first or the
    last character is wrong, so the time taken reveals nothing."""
    return hmac.compare_digest(typed.encode(), expected.encode())


def password_ok() -> bool:
    """True if the visitor may use the app. Otherwise the password form is
    shown and False is returned; the caller stops the page there."""
    expected = config.APP_PASSWORD
    if not expected or st.session_state.get("signed_in"):
        return True

    with st.container(key="password_panel"):
        st.html(brand(APP_NAME, size="large"))
        st.caption(APP_TAGLINE)
        with st.form("password_form", border=False):
            typed = st.text_input("Password", type="password", key="password_typed")
            if st.form_submit_button("Open", type="primary", icon=":material/lock_open:"):
                if password_matches(typed, expected):
                    st.session_state["signed_in"] = True
                    st.rerun()
                st.error("That is not the right password.")
    return False
