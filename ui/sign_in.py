"""The sign-in screen of a copy that has an invite code set.

On your own computer no invite code is set and the app opens directly, for
one user. A copy running in the cloud sets APP_PASSWORD, which is the
invite code: a visitor must then sign in to their own account, or create
one with the code, before anything else is shown or any API key is used.

Signing in lasts for one browser session.

The same screen handles a forgotten password: a form that emails a link,
and the page that link opens (its address ends in ?reset=...).
"""

import streamlit as st

from agent import accounts, config, mailer
from agent.accounts import Account, AccountError
from agent.config import APP_NAME, APP_TAGLINE
from agent.memory import backup_memory
from ui import runtime
from ui.assets import brand

# Said whether or not an email went out, so that the form does not reveal
# which usernames exist.
LINK_SENT = "If that account has an email address, a link is on its way. It works for 30 minutes."
MISMATCH = "The two new passwords are not the same."


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
    store = runtime.get_store()
    # A link for a forgotten password comes first, also for someone who is
    # signed in: they clicked it to set a new password.
    token = st.query_params.get("reset")
    if token:
        with _panel():
            _reset_page(store, token)
        return None

    signed_in = st.session_state.get("account")
    if signed_in:
        return Account(**signed_in)

    with _panel():
        notice = st.session_state.pop("sign_in_notice", None)
        if notice:
            st.success(notice)
        if st.session_state.get("forgot") and mailer.mail_is_set_up():
            _forgot_form(store)
        else:
            sign_in_tab, create_tab = st.tabs(["Sign in", "Create account"])
            with sign_in_tab:
                _sign_in_form(store)
            with create_tab:
                _create_form(store)
    return None


def _panel():
    """The card in the middle of the page, with the logo on top."""
    panel = st.container(key="sign_in_panel")
    with panel:
        st.html(brand(APP_NAME, size="large"))
        st.caption(APP_TAGLINE)
    return panel


def _go(forgot: bool) -> None:
    """Switch between the sign-in tabs and the "Forgot password?" form."""
    st.session_state["forgot"] = forgot


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
    # Offered only if this copy can send email.
    if mailer.mail_is_set_up():
        st.button("Forgot password?", key="forgot_link", type="tertiary", width="stretch",
                  on_click=_go, args=(True,))


def _create_form(store) -> None:
    with st.form("create_form", border=False):
        name = st.text_input("Your name", key="create_name", max_chars=40)
        username = st.text_input("Username", key="create_username", max_chars=30)
        email = st.text_input("Email", key="create_email", max_chars=254,
                              help="Only used to send you a link if you forget your password.")
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
                if not email.strip():
                    raise AccountError(accounts.BAD_EMAIL)
                account = accounts.create_account(store, username, name, password, email=email)
                # In the cloud the machine's disk is wiped on a restart, so
                # the new account is copied to the lasting folder at once.
                backup_memory()
                _remember(account, is_new=True)
            except AccountError as problem:
                st.error(str(problem))


# --- a forgotten password ------------------------------------------------------------------

def _forgot_form(store) -> None:
    st.markdown("**Reset your password**")
    with st.form("forgot_form", border=False):
        username = st.text_input("Username", key="forgot_username", max_chars=30)
        if st.form_submit_button("Email me a reset link", type="primary",
                                 icon=":material/mail:", width="stretch"):
            reset = accounts.start_reset(store, username)
            if reset:
                backup_memory()     # the link must survive a restart in the cloud
                mailer.send_later(mailer.reset_email(
                    reset.account.name, reset.account.username, reset.email,
                    mailer.reset_link(reset.token)))
            st.success(LINK_SENT)
    st.button("Back to sign in", key="forgot_back", type="tertiary", width="stretch",
              on_click=_go, args=(False,))


def _leave_reset_page(notice: str | None = None) -> None:
    """Drop the link from the page address and show the sign-in tabs."""
    del st.query_params["reset"]
    st.session_state["forgot"] = False
    if notice:
        st.session_state["sign_in_notice"] = notice


def _reset_page(store, token: str) -> None:
    account = accounts.account_for_reset(store, token)
    if account is None:
        st.error(accounts.LINK_DEAD)
        st.button("Back to sign in", key="reset_back", type="tertiary", width="stretch",
                  on_click=_leave_reset_page)
        return

    st.markdown("**Choose a new password**")
    st.caption(f"For the account {account.username}.")
    with st.form("reset_form", border=False):
        new = st.text_input("New password", type="password", key="reset_new",
                            help="At least 8 characters.")
        again = st.text_input("New password again", type="password", key="reset_again")
        if st.form_submit_button("Save new password", type="primary",
                                 icon=":material/lock_reset:", width="stretch"):
            try:
                if new != again:
                    raise AccountError(MISMATCH)
                accounts.finish_reset(store, token, new)
                backup_memory()
                # Whoever was signed in on this browser is signed out: the
                # new password is typed once, to prove it was noted.
                st.session_state.pop("account", None)
                _leave_reset_page("Password changed. Sign in with your new password.")
                st.rerun()
            except AccountError as problem:
                st.error(str(problem))
