"""The sign-in screen of a copy that has an invite code set.

On your own computer no invite code is set and the app opens directly, for
one user. A copy running in the cloud sets APP_PASSWORD, which is the
invite code: a visitor must then sign in to their own account, or create
one with the code, before anything else is shown or any API key is used.

Signing in lasts for one browser session.
"""

import streamlit as st

from agent import accounts, config
from agent.accounts import Account, AccountError
from agent.config import APP_NAME, APP_TAGLINE
from agent.memory import backup_memory
from ui import runtime
from ui.assets import brand


def accounts_are_on() -> bool:
    return bool(config.APP_PASSWORD)


def _remember(account: Account, is_new: bool = False) -> None:
    """Keep the account for this browser session and draw the page again,
    this time as the app."""
    st.session_state["account"] = {"username": account.username, "name": account.name}
    st.session_state["account_is_new"] = is_new
    st.rerun()


def current_account() -> Account | None:
    """The account signed in to this browser session. If there is none, the
    sign-in screen is shown and None is returned; the caller stops the page
    there."""
    signed_in = st.session_state.get("account")
    if signed_in:
        return Account(**signed_in)

    store = runtime.get_store()
    with st.container(key="sign_in_panel"):
        st.html(brand(APP_NAME, size="large"))
        st.caption(APP_TAGLINE)
        sign_in_tab, create_tab = st.tabs(["Sign in", "Create account"])
        with sign_in_tab:
            _sign_in_form(store)
        with create_tab:
            _create_form(store)
    return None


def _sign_in_form(store) -> None:
    with st.form("sign_in_form", border=False):
        username = st.text_input("Username", key="sign_in_username", max_chars=30)
        password = st.text_input("Password", type="password", key="sign_in_password")
        if st.form_submit_button("Sign in", type="primary", icon=":material/login:",
                                 width="stretch"):
            try:
                _remember(accounts.sign_in(store, username, password))
            except AccountError as problem:
                st.error(str(problem))


def _create_form(store) -> None:
    with st.form("create_form", border=False):
        name = st.text_input("Your name", key="create_name", max_chars=40)
        username = st.text_input("Username", key="create_username", max_chars=30)
        password = st.text_input("Password", type="password", key="create_password",
                                 help="At least 8 characters.")
        code = st.text_input("Invite code", type="password", key="create_code",
                             placeholder="The code you were given")
        if st.form_submit_button("Create account", type="primary",
                                 icon=":material/person_add:", width="stretch"):
            try:
                # The code is checked first: without it, the form says
                # nothing about which usernames exist.
                accounts.check_invite_code(store, code, config.APP_PASSWORD)
                account = accounts.create_account(store, username, name, password)
                # In the cloud the machine's disk is wiped on a restart, so
                # the new account is copied to the lasting folder at once.
                backup_memory()
                _remember(account, is_new=True)
            except AccountError as problem:
                st.error(str(problem))
