"""The assistant on the page: a small chat at the bottom right of every
view, for a quick question in between (agent/side_assistant.py).

It is closed at first and shows as one round button. Open, it is a panel
that floats over the page. Each conversation has its own chat, kept in the
browser session: it is gone after signing out or closing the tab.
"""

import streamlit as st

from agent import usage
from agent.config import MAX_QUESTION_CHARS
from agent.guards import check_question, friendly_error
from agent.side_assistant import ask
from agent.usage import Usage
from ui.assets import AVATAR, fill
from ui.texts import t

TITLE_MAX_CHARS = 34


def _chats() -> dict:
    return st.session_state.setdefault("assistant_chats", {})


def _open() -> None:
    st.session_state["assistant_is_open"] = True


def _close() -> None:
    st.session_state["assistant_is_open"] = False


def _new_chat(thread_id: str) -> None:
    _chats().pop(thread_id, None)


def render_assistant(thread_id: str, title: str, context: str, get_model) -> None:
    """Draw the assistant: its button, or its panel when it is open.

    title:     the open conversation's title, or "" for an empty one.
    context:   the report or answer that is open, or "".
    get_model: a function that returns the model to ask. It is called only
               when a question is sent.
    """
    if not st.session_state.get("assistant_is_open"):
        with st.container(key="assistant_launcher"):
            # Drawn as the robot's face alone (styles.css); pointing at it
            # says what it is.
            st.button(t("assistant.name"), key="assistant_open", help=t("assistant.open_help"),
                      on_click=_open)
        return

    chat = _chats().setdefault(thread_id, {"messages": [], "used": Usage()})
    with st.container(key="assistant_panel"):
        with st.container(key="assistant_head", horizontal=True, vertical_alignment="center"):
            shown = title if len(title) <= TITLE_MAX_CHARS else title[:TITLE_MAX_CHARS].rstrip() + "…"
            st.html(fill("helper_head.html",
                         title=t("assistant.title", title=shown) if shown
                         else t("assistant.name"),
                         scope=t("assistant.scope_report") if context
                         else t("assistant.scope_general")))
            st.button(t("assistant.new_chat"), key="assistant_new", type="tertiary",
                      on_click=_new_chat, args=(thread_id,))
            st.button("", icon=":material/remove:", key="assistant_close",
                      help=t("assistant.minimise"),
                      on_click=_close)

        thread = st.container(key="assistant_messages")
        with thread:
            if not chat["messages"]:
                st.html(fill("helper_empty.html",
                             text=t("assistant.empty_report") if context
                             else t("assistant.empty_general")))
            for number, message in enumerate(chat["messages"]):
                _message(number, message)

        question = st.chat_input(
            t("assistant.box_report") if context else t("assistant.box_general"),
            key="assistant_question", max_chars=MAX_QUESTION_CHARS)
        cost = usage.cost_text(chat["used"])
        st.caption(t("assistant.cost", cost=cost) if cost else t("assistant.not_added"))

    if not question:
        return
    problem = check_question(question)
    if problem:
        with thread:
            st.warning(problem)
        return
    asked = {"role": "user", "text": question.strip()}
    with thread:
        _message(len(chat["messages"]), asked)
        with st.spinner(t("assistant.thinking")):
            try:
                text, used = ask(get_model(), asked["text"], chat["messages"], context)
            except Exception as error:  # noqa: BLE001  (any failure is explained, not raised)
                text, used = friendly_error(error), Usage()
    chat["messages"] += [asked, {"role": "assistant", "text": text}]
    chat["used"] = chat["used"] + used
    # Draw the page again, so the answer and the cost are in their places.
    st.rerun()


def _message(number: int, message: dict) -> None:
    if message["role"] == "user":
        # fill() shows the words as text: they are typed by the user.
        st.html(fill("helper_question.html", question=message["text"]))
    else:
        # st.markdown shows any HTML in an answer as text.
        with st.chat_message("assistant", avatar=str(AVATAR)):
            st.markdown(message["text"])
