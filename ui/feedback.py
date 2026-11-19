"""The thumbs under an answer: "Was this helpful?" 👍 👎.

A thumbs down then asks what could be better: reasons to pick and a
comment. Once sent, a thank-you is shown and the question is not asked
again for that answer.

The views draw this through a function the page gives them (rater()), so
the views need not know about the store or the account.
"""

import streamlit as st

from agent.feedback import DOWN, REASONS, explain, rate, rating_line, run_of
from agent.trace_feedback import send_in_background
from agent.session import Turn
from ui.sidebar import chosen_settings
from ui.texts import current_language, t


def _save(store, user_id: str, thread_id: str, index: int, turn: Turn, key: str) -> None:
    """Runs when the thumbs are clicked, before the page is drawn again.

    The settings saved are the ones chosen now: the answer was almost
    always written with them, as they rarely change between an answer and
    its rating."""
    rating = st.session_state.get(key)
    rate(store, user_id, thread_id, index, rating, question=turn.question,
         settings=chosen_settings(), report=bool(turn.answer and turn.answer.report))
    send_in_background(run_of(store, user_id, thread_id, index), rating, [], "")


def _send(store, user_id: str, thread_id: str, index: int) -> None:
    """Runs when "Send feedback" is clicked."""
    suffix = f"{thread_id}_{index}"
    explain(store, user_id, thread_id, index, st.session_state.get(f"why_{suffix}") or [],
            st.session_state.get(f"why_comment_{suffix}", ""))
    line = rating_line(store, user_id, thread_id, index) or {}
    send_in_background(run_of(store, user_id, thread_id, index), line.get("rating"),
                       line.get("reasons", []), line.get("comment", ""))
    st.session_state[f"why_thanks_{suffix}"] = True


def _ask_why(store, user_id: str, thread_id: str, index: int) -> None:
    """The panel shown after a thumbs down."""
    suffix = f"{thread_id}_{index}"
    language = current_language()       # format_func runs after the page is drawn
    with st.container(key=f"why_panel_{index}", border=True):
        st.markdown(f"**{t('feedback.why')}** :gray[{t('feedback.pick')}]")
        st.pills(t("feedback.why"), list(REASONS), selection_mode="multi", key=f"why_{suffix}",
                 format_func=lambda reason: t(f"feedback.reason.{reason}", language=language),
                 label_visibility="collapsed")
        st.text_area(t("feedback.comment"), key=f"why_comment_{suffix}", height=68,
                     placeholder=t("feedback.comment"), label_visibility="collapsed")
        st.button(t("feedback.send"), key=f"why_send_{suffix}", type="primary",
                  icon=":material/check:", on_click=_send, args=(store, user_id, thread_id, index))


def render_rating(store, user_id: str, thread_id: str, index: int, turn: Turn) -> None:
    key = f"rate_{thread_id}_{index}"
    line = rating_line(store, user_id, thread_id, index)
    with st.container(key=f"rating_{index}", horizontal=True, horizontal_alignment="right",
                      vertical_alignment="center", gap="small"):
        st.caption(t("feedback.ask"), width="content")
        st.feedback("thumbs", key=key, default=line["rating"] if line else None,
                    on_change=_save, args=(store, user_id, thread_id, index, turn, key))
    if st.session_state.pop(f"why_thanks_{thread_id}_{index}", False):
        st.success(t("feedback.thanks"), icon=":material/check:")
    elif line and line["rating"] == DOWN and "reasons" not in line:
        _ask_why(store, user_id, thread_id, index)


def rater(store, user_id: str, thread_id: str):
    """The function the views call to draw the thumbs of one answer."""
    return lambda index, turn: render_rating(store, user_id, thread_id, index, turn)
