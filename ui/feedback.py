"""The thumbs under an answer: "Was this helpful?" 👍 👎.

The views draw them through a function the page gives them (rater()), so
the views need not know about the store or the account.
"""

import streamlit as st

from agent.feedback import rate, rating_of
from agent.session import Turn
from ui.sidebar import chosen_settings
from ui.texts import t


def _save(store, user_id: str, thread_id: str, index: int, turn: Turn, key: str) -> None:
    """Runs when the thumbs are clicked, before the page is drawn again.

    The settings saved are the ones chosen now: the answer was almost
    always written with them, as they rarely change between an answer and
    its rating."""
    rate(store, user_id, thread_id, index, st.session_state.get(key), question=turn.question,
         settings=chosen_settings(), report=bool(turn.answer and turn.answer.report))


def render_rating(store, user_id: str, thread_id: str, index: int, turn: Turn) -> None:
    key = f"rate_{thread_id}_{index}"
    with st.container(key=f"rating_{index}", horizontal=True, horizontal_alignment="right",
                      vertical_alignment="center", gap="small"):
        st.caption(t("feedback.ask"), width="content")
        st.feedback("thumbs", key=key, default=rating_of(store, user_id, thread_id, index),
                    on_change=_save, args=(store, user_id, thread_id, index, turn, key))


def rater(store, user_id: str, thread_id: str):
    """The function the views call to draw the thumbs of one answer."""
    return lambda index, turn: render_rating(store, user_id, thread_id, index, turn)
