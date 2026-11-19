"""The round badge at the top right of the page for the signed-in account.

It shows the first letter of the person's name. Clicking it opens a small
menu that says who is signed in and offers "Sign out". The stylesheet
makes it round and keeps it in the corner (see "The account badge").
"""

import streamlit as st

from agent.accounts import Account
from ui.assets import fill
from ui.texts import t


def initial_of(name: str) -> str:
    """The letter on the badge."""
    return name.strip()[:1].upper() or "?"


def render_account_badge(account: Account) -> bool:
    """Show the badge. Returns True if "Sign out" was pressed."""
    with st.container(key="account_badge"):
        with st.popover(initial_of(account.name)):
            # The name was typed by a person: fill() shows it as text.
            st.html(fill("account.html", label=t("account.signed_in_as"), person=account.name))
            return st.button(t("account.sign_out"), icon=":material/logout:", key="sign_out",
                             type="tertiary")
