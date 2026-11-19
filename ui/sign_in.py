"""The sign-in screen of a copy that has an invite code set.

On your own computer no invite code is set and the app opens directly, for
one user. A copy running in the cloud sets APP_PASSWORD, which is the
invite code: a visitor must then sign in to their own account, or create
one with the code, before anything else is shown or any API key is used.

Signing in lasts for one browser session.

The same screen is where a password or an email address is changed, and
where a forgotten password is dealt with: a form that emails a link, and
the page that link opens (its address ends in ?reset=...). None of these
needs the person to be signed in; the two changes ask for the username and
the current password instead.
"""

import streamlit as st

from agent import accounts, config, mailer
from agent.accounts import Account, AccountError
from agent.config import APP_NAME, APP_TAGLINE
from agent.memory import backup_memory
from ui import runtime
from ui.assets import brand
from ui.texts import t

# Said whether or not an email went out, so that the form does not reveal
# which usernames exist.
LINK_SENT = "If that account has an email address, a link is on its way. It works for 30 minutes."
MISMATCH = "The two new passwords are not the same."

# The messages of agent/accounts.py, by the name of their text in ui/words.
ACCOUNT_MESSAGES = {
    accounts.NO_MATCH: "account.err.no_match", accounts.MUST_WAIT: "account.err.must_wait",
    accounts.WRONG_CODE: "account.err.wrong_code", accounts.NOT_CURRENT: "account.err.not_current",
    accounts.BAD_EMAIL: "account.err.bad_email", accounts.LINK_DEAD: "account.err.link_dead",
    accounts.BAD_USERNAME: "account.err.bad_username",
    f"Use a password of at least {accounts.PASSWORD_MIN_CHARS} characters.": "account.err.short",
    f"Use a password of at most {accounts.PASSWORD_MAX_CHARS} characters.": "account.err.long",
    "Enter your name.": "account.err.name",
    "That username is taken. Choose another.": "account.err.taken",
    "Choose a password that differs from the current one.": "account.err.same",
    MISMATCH: "signin.mismatch",
}


def message(problem) -> str:
    """An account message in the chosen language."""
    text = str(problem)
    return t(ACCOUNT_MESSAGES[text]) if text in ACCOUNT_MESSAGES else text


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
        view = st.session_state.get("sign_in_view")
        if view == FORGOT and mailer.mail_is_set_up():
            _forgot_form(store)
        elif view == PASSWORD:
            _change_password_form(store)
        elif view == EMAIL:
            _change_email_form(store)
        else:
            sign_in_tab, create_tab = st.tabs([t("signin.tab_sign_in"), t("signin.tab_create")])
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


# What the card shows in place of the two tabs.
FORGOT, PASSWORD, EMAIL = "forgot", "password", "email"


def _go(view: str | None, notice: str | None = None) -> None:
    """Show one of the forms in place of the two tabs, or (None) the tabs
    again, optionally with a line saying what was just done."""
    st.session_state["sign_in_view"] = view
    if notice:
        st.session_state["sign_in_notice"] = notice


def _back_button(key: str) -> None:
    st.button(t("signin.back"), key=key, type="tertiary", width="stretch",
              on_click=_go, args=(None,))


def _as_on_sign_in(problem: AccountError) -> str:
    """The message for a refused change. Here nobody is signed in, so a
    wrong password is worded as on the sign-in form: it must not reveal
    whether the username exists."""
    return message(accounts.NO_MATCH if str(problem) == accounts.NOT_CURRENT else problem)


def _sign_in_form(store) -> None:
    with st.form("sign_in_form", border=False):
        username = st.text_input(t("signin.username"), key="sign_in_username", max_chars=30)
        password = st.text_input(t("signin.password"), type="password", key="sign_in_password")
        if st.form_submit_button(t("signin.sign_in"), type="primary", icon=":material/login:",
                                 width="stretch"):
            try:
                _remember(accounts.sign_in(store, username, password))
            except AccountError as problem:
                st.error(message(problem))
    # Small links under the form. "Forgot password?" is offered only if
    # this copy can send email.
    links = [(t("signin.change_password"), PASSWORD), (t("signin.change_email"), EMAIL)]
    if mailer.mail_is_set_up():
        links.insert(0, (t("signin.forgot"), FORGOT))
    with st.container(key="sign_in_links", horizontal=True, horizontal_alignment="center"):
        for label, view in links:
            st.button(label, key=f"{view}_link", type="tertiary", on_click=_go, args=(view,))


def _create_form(store) -> None:
    with st.form("create_form", border=False):
        name = st.text_input(t("signin.your_name"), key="create_name", max_chars=40)
        username = st.text_input(t("signin.username"), key="create_username", max_chars=30)
        email = st.text_input(t("signin.email"), key="create_email", max_chars=254,
                              help=t("signin.email_help"))
        password = st.text_input(t("signin.password"), type="password", key="create_password",
                                 help=t("signin.password_help"))
        code = st.text_input(t("signin.invite"), type="password", key="create_code",
                             placeholder=t("signin.invite_example"))
        if st.form_submit_button(t("signin.create"), type="primary",
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
                st.error(message(problem))


# --- a forgotten password ------------------------------------------------------------------

def _forgot_form(store) -> None:
    st.markdown(t("signin.reset_title"))
    with st.form("forgot_form", border=False):
        username = st.text_input(t("signin.username"), key="forgot_username", max_chars=30)
        if st.form_submit_button(t("signin.reset_send"), type="primary",
                                 icon=":material/mail:", width="stretch"):
            reset = accounts.start_reset(store, username)
            if reset:
                backup_memory()     # the link must survive a restart in the cloud
                mailer.send_later(mailer.reset_email(
                    reset.account.name, reset.account.username, reset.email,
                    mailer.reset_link(reset.token)))
            st.success(t("signin.link_sent"))
    _back_button("forgot_back")


def _leave_reset_page(notice: str | None = None) -> None:
    """Drop the link from the page address and show the sign-in tabs."""
    del st.query_params["reset"]
    _go(None, notice)


def _reset_page(store, token: str) -> None:
    account = accounts.account_for_reset(store, token)
    if account is None:
        st.error(message(accounts.LINK_DEAD))
        st.button(t("signin.back"), key="reset_back", type="tertiary", width="stretch",
                  on_click=_leave_reset_page)
        return

    st.markdown(t("signin.choose_new"))
    st.caption(t("signin.for_account", username=account.username))
    with st.form("reset_form", border=False):
        new = st.text_input(t("signin.new_password"), type="password", key="reset_new",
                            help=t("signin.password_help"))
        again = st.text_input(t("signin.new_again"), type="password", key="reset_again")
        if st.form_submit_button(t("signin.save_password"), type="primary",
                                 icon=":material/lock_reset:", width="stretch"):
            try:
                if new != again:
                    raise AccountError(MISMATCH)
                accounts.finish_reset(store, token, new)
                backup_memory()
                # Whoever was signed in on this browser is signed out: the
                # new password is typed once, to prove it was noted.
                st.session_state.pop("account", None)
                _leave_reset_page(t("signin.password_changed"))
                st.rerun()
            except AccountError as problem:
                st.error(message(problem))


# --- changing the password or the email address ----------------------------------------------

def _change_password_form(store) -> None:
    st.markdown(t("signin.change_password_title"))
    with st.form("change_password_form", border=False):
        username = st.text_input(t("signin.username"), key="cp_username", max_chars=30)
        current = st.text_input(t("signin.current_password"), type="password", key="cp_current")
        new = st.text_input(t("signin.new_password"), type="password", key="cp_new",
                            help=t("signin.password_help"))
        again = st.text_input(t("signin.new_again"), type="password", key="cp_again")
        if st.form_submit_button(t("signin.save_password"), type="primary",
                                 icon=":material/key:", width="stretch"):
            try:
                if new != again:
                    raise AccountError(MISMATCH)
                accounts.change_password(store, username, current, new)
                backup_memory()     # kept across a restart in the cloud
                _go(None, t("signin.password_changed"))
                st.rerun()
            except AccountError as problem:
                st.error(_as_on_sign_in(problem))
    _back_button("cp_back")


def _change_email_form(store) -> None:
    st.markdown(t("signin.email_title"))
    st.caption(t("signin.email_caption"))
    with st.form("change_email_form", border=False):
        username = st.text_input(t("signin.username"), key="em_username", max_chars=30)
        password = st.text_input(t("signin.current_password"), type="password", key="em_password")
        email = st.text_input(t("signin.new_email"), key="em_email", max_chars=254)
        if st.form_submit_button(t("signin.save_email"), type="primary",
                                 icon=":material/mail:", width="stretch"):
            try:
                # The address is looked at first, so a typing mistake in it
                # does not count as a wrong try at the password.
                address = accounts.clean_email(email)
                accounts.set_email(store, username, password, address)
                backup_memory()
                _go(None, t("signin.email_saved", address=address))
                st.rerun()
            except AccountError as problem:
                st.error(_as_on_sign_in(problem))
    _back_button("em_back")
