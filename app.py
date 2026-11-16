"""The web app.

    streamlit run app.py

Streamlit runs this file from top to bottom every time the user does
something. Nothing important is kept in the page itself: the conversation
is read from the agent's saved state on each run, and the conversation id
lives in the page address (?c=...), so a refresh shows the same chat.
"""

import streamlit as st

from agent.config import APP_NAME, MissingKeyError
from agent.session import list_conversations, load_messages, new_thread_id, to_blocks
from agent.agent import pending_pause
from ui.approvals import render_pause
from ui.chat import render_history, run_resume, run_turn
from ui.guide import render_guide
from ui.runtime import get_runtime
from ui.sidebar import render_sidebar
from ui.start import OPEN_GUIDE, render_start_screen
from ui.styles import apply_styles

st.set_page_config(page_title=APP_NAME, page_icon=":material/travel_explore:",
                   layout="centered", initial_sidebar_state="collapsed")
apply_styles()

# --- the agent -------------------------------------------------------------------------
try:
    runtime = get_runtime()
except MissingKeyError as error:
    st.title(APP_NAME, anchor=False)
    st.error(str(error), title="Setup needed")
    st.markdown(
        "1. Copy `.env.example` to `.env` in the project folder.\n"
        "2. Paste your OpenRouter and Tavily keys into it.\n"
        "3. Restart the app."
    )
    st.stop()

# --- which conversation -------------------------------------------------------------------
# The id is kept in the page address so that a refresh, or a bookmarked
# link, opens the same conversation.
if "c" not in st.query_params:
    st.query_params["c"] = new_thread_id()
thread_id = st.query_params["c"]

action = render_sidebar(list_conversations(runtime.agent, runtime.checkpointer), thread_id)
if action == "new":
    st.query_params["c"] = new_thread_id()
    st.rerun()
elif action:
    st.query_params["c"] = action
    st.rerun()

# --- the conversation ------------------------------------------------------------------------
blocks = to_blocks(load_messages(runtime.agent, thread_id))

# Is the agent stopped, waiting for an approval? This is read from the
# saved state, so the form comes back after a refresh or a restart.
waiting = pending_pause(runtime.agent, thread_id)

question = st.chat_input(
    "Answer the question above to continue" if waiting else "Ask about a market",
    key="question", submit_mode="disable", disabled=waiting is not None)

# The "How it works" guide is shown for this conversation only, and only
# until a real question is asked. It lives in the browser session, not in
# the saved conversation.
guide = st.session_state.get("guide")
guide = guide if guide and guide["thread"] == thread_id else None

if not blocks:
    # An empty conversation shows the start screen or the guide. Either
    # sits in a placeholder so it can be removed once a question is asked.
    front = st.empty()
    with front.container():
        if guide and not question:
            chosen = render_guide(guide)
            if chosen == "back":
                st.session_state.pop("guide", None)
                st.rerun()
            question = chosen
        else:
            chosen = render_start_screen()
            if chosen == OPEN_GUIDE:
                st.session_state["guide"] = {"thread": thread_id, "topics": ["how"],
                                             "scroll": True}
                st.rerun()
            question = chosen or question
    if question:
        front.empty()
        st.session_state.pop("guide", None)
else:
    # A button inside the conversation (such as "Save to reports folder")
    # sends a question, just as typing it would.
    pressed = render_history(blocks)
    if not waiting:
        question = question or pressed

if waiting:
    # Show the approval form. When it is submitted, continue the agent with
    # the answer, then draw the page again from the saved state: that shows
    # either the result or the next approval.
    form = st.empty()
    with form.container():
        answer = render_pause(waiting)
    if answer is not None:
        form.empty()
        run_resume(runtime.agent, thread_id, answer)
        st.rerun()
elif question:
    run_turn(runtime.agent, thread_id, question)
    st.rerun()
