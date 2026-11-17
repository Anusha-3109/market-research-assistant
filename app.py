"""The web app.

    streamlit run app.py

Streamlit runs this file from top to bottom every time the user does
something. Nothing important is kept in the page itself: the conversation
is read from the agent's saved state on each run, and the conversation id
lives in the page address (?c=...), so a refresh shows the same chat.
"""

import streamlit as st

from agent.agent import pending_pause, settle_stopped_turn
from agent.config import APP_NAME, MAX_QUESTION_CHARS, MissingKeyError
from agent.guards import check_question
from agent.memory import (
    DEFAULT_USER,
    UserContext,
    backup_memory,
    forget_profile,
    load_profile,
)
from agent.session import (
    list_conversations,
    load_messages,
    new_thread_id,
    to_blocks,
    to_turns,
)
from ui.assets import LOGO
from ui.guide import render_guide
from ui.password import password_ok
from ui.research import render_tabs, render_turn, run_live
from ui.runtime import get_runtime
from ui.sidebar import FORGET, GUIDE, NEW, current_settings, render_sidebar
from ui.picker import BACK, open_picker, render_picker
from ui.start import OPEN_GUIDE, OPEN_PICKER, render_start_screen
from ui.styles import apply_styles

st.set_page_config(page_title=APP_NAME, page_icon=str(LOGO),
                   layout="centered", initial_sidebar_state="collapsed")
apply_styles()

# A deployed copy asks for a password before anything else happens.
if not password_ok():
    st.stop()

# --- the agent -------------------------------------------------------------------------
# The settings chosen in the sidebar decide which agent is used. They also
# travel with every request, so the report workflow follows them too.
settings = current_settings()
try:
    runtime = get_runtime(settings["model_name"], settings["temperature"])
except MissingKeyError as error:
    st.title(APP_NAME, anchor=False)
    st.error(str(error), title="Setup needed")
    st.markdown(
        "1. Copy `.env.example` to `.env` in the project folder.\n"
        "2. Paste your OpenRouter and Tavily keys into it.\n"
        "3. Restart the app."
    )
    st.stop()

context = UserContext(user_id=DEFAULT_USER, **settings)

# --- which conversation -------------------------------------------------------------------
# The id is kept in the page address so that a refresh, or a bookmarked
# link, opens the same conversation.
if "c" not in st.query_params:
    st.query_params["c"] = new_thread_id()
thread_id = st.query_params["c"]

# Is the agent stopped, waiting for an approval? This is read from the
# saved state, so the form comes back after a refresh or a restart.
waiting = pending_pause(runtime.agent, thread_id)

# A turn that was cut off (Stop was pressed, or the page was closed while a
# tool was running) is tidied here so the conversation can continue.
if waiting is None and settle_stopped_turn(runtime.agent, thread_id):
    backup_memory()
    st.toast("Stopped. What was found so far is kept.", icon=":material/stop_circle:")
st.session_state.pop("stopped", None)


def open_guide(for_thread: str) -> None:
    st.session_state["guide"] = {"thread": for_thread, "topics": ["how"], "scroll": True}


action = render_sidebar(
    list_conversations(runtime.agent, runtime.checkpointer), thread_id,
    profile=load_profile(runtime.store, DEFAULT_USER), waiting=waiting is not None)
if action == NEW:
    st.query_params["c"] = new_thread_id()
    st.rerun()
elif action == FORGET:
    forget_profile(runtime.store, DEFAULT_USER)
    backup_memory()
    st.toast("Everything remembered about you was deleted.", icon=":material/check:")
    st.rerun()
elif action == GUIDE:
    # The guide belongs to an empty conversation, so open a new one for it.
    fresh = new_thread_id()
    st.query_params["c"] = fresh
    open_guide(fresh)
    st.rerun()
elif action:
    st.query_params["c"] = action
    st.rerun()

# --- the conversation ------------------------------------------------------------------------
# Each question with its answer is one "turn". The research view shows one
# turn at a time; the others are tabs.
turns = to_turns(to_blocks(load_messages(runtime.agent, thread_id)))

# A picker screen, opened by clicking a start card, belongs to one empty
# conversation and lives in the browser session, like the guide below.
picker = st.session_state.get("picker")
picker = picker if picker and picker["thread"] == thread_id and not turns else None

# The picker has its own box in the middle of the page, so the question box
# at the bottom is left out while one is open.
question = None
if not picker:
    question = st.chat_input(
        "Answer the question above to continue" if waiting
        else "Ask a follow-up" if turns else "Ask about a market",
        key="question", submit_mode="disable", disabled=waiting is not None,
        max_chars=MAX_QUESTION_CHARS)

# The "How it works" guide is shown for this conversation only, and only
# until a real question is asked. It lives in the browser session, not in
# the saved conversation.
guide = st.session_state.get("guide")
guide = guide if guide and guide["thread"] == thread_id else None

# The start screen or a finished answer is drawn in one placeholder and the
# live view in a second one below it. To go live, the first is emptied and
# the second filled. (Filling one placeholder twice in the same run breaks
# the page in the browser.)
view = st.empty()
live = st.empty()
answer = None           # the answer to an approval form, once submitted

if not turns:
    # An empty conversation shows the start screen, the guide, or the picker
    # of the start card that was clicked.
    with view.container():
        if guide and not question:
            chosen = render_guide(guide)
            if chosen == "back":
                st.session_state.pop("guide", None)
                st.rerun()
            question = chosen
        elif picker and not question:
            chosen = render_picker(picker)
            if chosen == BACK:
                st.session_state.pop("picker", None)
                st.rerun()
            question = chosen
        else:
            chosen = render_start_screen()
            if chosen == OPEN_GUIDE:
                open_guide(thread_id)
                st.rerun()
            if chosen and chosen.startswith(OPEN_PICKER):
                open_picker(thread_id, chosen.removeprefix(OPEN_PICKER))
                st.rerun()
    if question:
        st.session_state.pop("guide", None)
        st.session_state.pop("picker", None)
elif not question:
    with view.container():
        shown = render_tabs(turns, thread_id, locked=waiting is not None)
        is_latest = shown == len(turns) - 1
        outcome = render_turn(turns[shown], shown, thread_id, is_latest,
                              waiting if is_latest else None)
    if outcome.new:
        st.query_params["c"] = new_thread_id()
        st.rerun()
    # A button in the view (such as "Save to reports folder") sends a
    # question, just as typing it would.
    question, answer = outcome.question, outcome.answer

# A message that is empty or far too long is turned back here, before it
# costs anything.
if question:
    problem = check_question(question)
    if problem:
        st.warning(problem)
        question = None

# Run the agent in the live view, then draw the page again from the saved
# state: that shows the answer, or the next approval form.
if answer is not None:
    latest = turns[-1]
    view.empty()
    with live.container():
        run_live(runtime.agent, thread_id, context, title=latest.question,
                 turn_index=len(turns) - 1, answer=answer,
                 earlier_steps=latest.answer.activity if latest.answer else [])
    # A deployed copy keeps a copy of the memory file after every answer.
    backup_memory()
    st.rerun()
elif question and not waiting:
    view.empty()
    with live.container():
        run_live(runtime.agent, thread_id, context, title=question,
                 turn_index=len(turns), question=question)
    # A deployed copy keeps a copy of the memory file after every answer.
    backup_memory()
    st.rerun()
