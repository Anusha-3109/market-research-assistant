"""The rows at the foot of the sidebar for the signed-in account: who is
signed in, signing out, changing the password, and the email address that
a link for a forgotten password is sent to."""

import streamlit as st

from agent import accounts
from agent.accounts import Account, AccountError
from agent.memory import backup_memory
from ui import runtime
from ui.assets import fill
from ui.sign_in import MISMATCH


def render_account_rows(account: Account) -> bool:
    """Show the rows. Returns True if "Sign out" was pressed."""
    # The name was typed by a person: fill() shows it as text.
    st.html(fill("account.html", person=account.name))
    signed_out = st.button("Sign out", icon=":material/logout:", key="sign_out", type="tertiary")
    store = runtime.get_store()
    _change_password(store, account)
    _email(store, account)
    return signed_out


def _change_password(store, account: Account) -> None:
    with st.expander("Change password", icon=":material/key:"):
        with st.form("change_password_form", border=False, clear_on_submit=True):
            current = st.text_input("Current password", type="password", key="cp_current")
            new = st.text_input("New password", type="password", key="cp_new",
                                help="At least 8 characters.")
            again = st.text_input("New password again", type="password", key="cp_again")
            if st.form_submit_button("Change password", width="stretch"):
                try:
                    if new != again:
                        raise AccountError(MISMATCH)
                    accounts.change_password(store, account.username, current, new)
                    backup_memory()     # kept across a restart in the cloud
                    st.success("Password changed.")
                except AccountError as problem:
                    st.error(str(problem))


def _email(store, account: Account) -> None:
    with st.expander("Email for password reset", icon=":material/mail:"):
        on_file = accounts.email_of(store, account.username)
        st.caption(f"On file: {on_file}" if on_file else
                   "No email address yet. Without one, a forgotten password cannot be reset.")
        with st.form("email_form", border=False, clear_on_submit=True):
            email = st.text_input("New email address", key="em_email", max_chars=254)
            password = st.text_input("Current password", type="password", key="em_password")
            if st.form_submit_button("Save email", width="stretch"):
                try:
                    accounts.set_email(store, account.username, password, email)
                    backup_memory()
                    st.success("Email address saved.")
                except AccountError as problem:
                    st.error(str(problem))
