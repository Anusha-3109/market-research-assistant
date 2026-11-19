"""The round badge at the bottom of the sidebar for the signed-in account.

It shows the first letter of the person's name. Clicking it opens a small
menu that says who is signed in and offers "Sign out". The stylesheet
makes it round (see "The account badge").
"""

import streamlit as st

from agent.accounts import Account
from ui.assets import fill
from ui.texts import t


def initial_of(name: str) -> str:
    """The letter on the badge."""
    return name.strip()[:1].upper() or "?"


def _sign_out() -> None:
    """Everything this browser session held goes: who was signed in, their
    settings, and the address of the conversation that was open. The page
    is then drawn again, as the sign-in screen."""
    st.session_state.clear()
    st.query_params.clear()


def render_account_badge(account: Account) -> None:
    """Show the badge. Called inside the sidebar, under Help."""
    with st.container(key="account_badge", horizontal=True, vertical_alignment="center"):
        with st.popover(initial_of(account.name)):
            # The name was typed by a person: fill() shows it as text.
            st.html(fill("account.html", label=t("account.signed_in_as"), person=account.name))
            st.button(t("account.sign_out"), icon=":material/logout:", key="sign_out",
                      type="tertiary", on_click=_sign_out)
        st.html(fill("account_name.html", person=account.name,
                     line=t("account.signed_in_line", username=account.username)))
