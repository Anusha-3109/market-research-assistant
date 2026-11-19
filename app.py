"""The web app.

    streamlit run app.py

Streamlit runs this file from top to bottom every time the user does
something. Nothing important is kept in the page itself: the conversation
is read from the agent's saved state on each run, and the conversation id
lives in the page address (?c=...), so a refresh shows the same chat.
"""

import streamlit as st

from agent import usage_log
from agent.app_settings import SHARED, load_app_settings
from agent.agent import pending_pause, settle_stopped_turn
from agent.config import APP_NAME, MAX_QUESTION_CHARS, MissingKeyError
from agent.guards import check_question
from agent.memory import (
    DEFAULT_USER,
    UserContext,
    backup_memory,
    clean_settings,
    forget_profile,
    load_profile,
    load_settings,
    save_settings,
)
from agent.session import (
    adopt_existing,
    claim_conversation,
    list_conversations,
    load_messages,
    may_open,
    new_thread_id,
    report_title,
    short_title,
    to_blocks,
    to_turns,
)
from ui.assistant import render_assistant
from ui.assets import LOGO
from ui.guide import render_guide
from ui.language import render_language_switch
from ui.page_sidebar import render_page_sidebar
from ui.dashboard import render_dashboard
from ui.admin import render_admin
from ui.pages import ADMIN, DASHBOARD, RESEARCH, current_page
from ui.texts import t
from ui.research import (
    question_box_text,
    render_ask_view,
    render_report_view,
    render_snapshot_view,
    run_live,
)
from ui.runtime import get_runtime, get_side_model, get_store
from ui.sidebar import (
    FORGET,
    GUIDE,
    ASK,
    NEW,
    REPORT,
    SNAPSHOT,
    chosen_settings,
    current_settings,
    current_view,
    prepare_settings,
    render_sidebar,
)
from ui.sign_in import accounts_are_on, current_account
from ui.picker import BACK, open_picker, render_picker
from ui.start import OPEN_GUIDE, OPEN_PICKER, render_start_screen
from ui.styles import apply_styles

st.set_page_config(page_title=APP_NAME, page_icon=str(LOGO),
                   layout="centered", initial_sidebar_state="collapsed")
apply_styles()

# A deployed copy asks the visitor to sign in before anything else happens.
# On your own computer there are no accounts and one user.
account = current_account() if accounts_are_on() else None
if accounts_are_on() and account is None:
    # The sign-in screen has the language switch too.
    render_language_switch()
    st.stop()
user_id = account.user_id if account else DEFAULT_USER

# --- the settings ----------------------------------------------------------------------
# An account's settings are put in place once, right after signing in, and
# saved again whenever one is changed.
if account and not st.session_state.get("settings_restored"):
    prepare_settings(load_settings(get_store(), user_id))
    st.session_state["settings_restored"] = True
else:
    prepare_settings()
if account:
    chosen = clean_settings(chosen_settings())
    if chosen != load_settings(get_store(), user_id):
        save_settings(get_store(), user_id, chosen)
        backup_memory()
# The model settings, the system prompt and the tools are set on the Admin
# page for every account (agent/app_settings.py). They are read on every
# run, so a change there reaches everyone with their next click.
app_settings = load_app_settings(get_store())
for name in SHARED:
    st.session_state[f"set_{name}"] = app_settings[name]

# --- the agent -------------------------------------------------------------------------
# The settings chosen in the sidebar decide which agent is used. They also
# travel with every request, so the report workflow follows them too.
settings = current_settings()
try:
    runtime = get_runtime(settings["model_name"], settings["temperature"],
                          disabled_tools=tuple(app_settings["disabled_tools"]))
except MissingKeyError as error:
    st.title(APP_NAME, anchor=False)
    st.error(str(error), title="Setup needed")
    st.markdown(
        "1. Copy `.env.example` to `.env` in the project folder.\n"
        "2. Paste your OpenRouter and Tavily keys into it.\n"
        "3. Restart the app."
    )
    st.stop()

context = UserContext(user_id=user_id, **settings)

# The language switch, at the top right. It is drawn after the account's
# settings are in place, so it shows the language that account chose.
render_language_switch()

# --- the other pages -------------------------------------------------------------------------
# Dashboard and Admin are drawn in place of the research pages; the links
# at the top of the sidebar open them. How it works is in Admin's
# Documentation tab.
open_page = current_page(account)
if open_page != RESEARCH:
    render_page_sidebar(open_page, account)
    if open_page == ADMIN:
        render_admin(runtime.store)
    elif open_page == DASHBOARD:
        # Each account sees its own use; without accounts, all of it.
        render_dashboard(runtime.store, user_id if account else None)
    st.stop()

# What was saved before there were accounts goes to the first account that
# opens the app. This is done once.
if account and adopt_existing(runtime.store, runtime.checkpointer, user_id):
    backup_memory()

# --- which conversation -------------------------------------------------------------------
# The id is kept in the page address so that a refresh, or a bookmarked
# link, opens the same conversation.
if "c" not in st.query_params:
    st.query_params["c"] = new_thread_id()
thread_id = st.query_params["c"]

# The address of a conversation is not a key to it: a conversation that
# belongs to another account is not opened. An empty one is opened instead.
if account and not may_open(runtime.agent, runtime.store, thread_id, user_id):
    st.query_params["c"] = new_thread_id()
    st.rerun()

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


# --- the conversation ------------------------------------------------------------------------
# Each question with its answer is one "turn". It is read here, before the
# sidebar is drawn, because the sidebar shows the views this conversation has.
turns = to_turns(to_blocks(load_messages(runtime.agent, thread_id)))
# Every open conversation has the Ask view. One that holds a report has
# the Report view as well, and the Snapshot view if the report's key figures
# were kept with it.
reports = [turn.answer for turn in turns if turn.answer is not None and turn.answer.report]
views = [ASK] if turns else []
if reports:
    views.append(REPORT)
    if reports[-1].snapshot:
        views.insert(0, SNAPSHOT)
# A conversation whose newest answer is a report opens on its snapshot;
# any other opens on Ask. While an approval is waiting, its form is on the
# Ask view.
# (Named open_view: further down, `view` is the placeholder the page is drawn in.)
newest_is_report = bool(turns and turns[-1].answer is not None and turns[-1].answer.report)
open_view = ASK if waiting is not None else current_view(
    thread_id, views, default=SNAPSHOT if newest_is_report else ASK)

action = render_sidebar(
    list_conversations(runtime.agent, runtime.checkpointer, store=runtime.store,
                       user_id=user_id if account else None), thread_id,
    profile=load_profile(runtime.store, user_id), waiting=waiting is not None,
    title=short_title(turns[0].question) if turns else "", views=views,
    shown_view=open_view, account=account)
if action == NEW:
    st.query_params["c"] = new_thread_id()
    st.rerun()
elif action == FORGET:
    forget_profile(runtime.store, user_id)
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


# A picker screen, opened by clicking a start card, belongs to one empty
# conversation and lives in the browser session, like the guide below.
picker = st.session_state.get("picker")
picker = picker if picker and picker["thread"] == thread_id and not turns else None

# The picker has its own box in the middle of the page, so the question box
# at the bottom is left out while one is open.
# An approval form that was just submitted. The answer is kept for one run
# and the page drawn again, so that the question box below can already say
# that work is under way: a box is drawn before the form, and without this
# step it would still read "Answer the question above" while the report
# continues.
resuming = st.session_state.pop("resume", None)
resuming = resuming if resuming and resuming["thread"] == thread_id and waiting else None

# The question box, kept at the bottom of the window. A picker has its own
# box, and the Snapshot and Report views have none: questions are asked in
# the Ask view.
question = None
if not picker and open_view == ASK:
    question = st.chat_input(
        question_box_text(bool(resuming), waiting is not None, bool(turns)),
        key="question", submit_mode="disable",
        disabled=waiting is not None, max_chars=MAX_QUESTION_CHARS)

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
            hello = t("start.welcome") if st.session_state.get("account_is_new") else t("start.welcome_back")
            chosen = render_start_screen(greeting=(hello, account.name) if account else None)
            if chosen == OPEN_GUIDE:
                open_guide(thread_id)
                st.rerun()
            if chosen and chosen.startswith(OPEN_PICKER):
                open_picker(thread_id, chosen.removeprefix(OPEN_PICKER))
                st.rerun()
    if question:
        st.session_state.pop("guide", None)
        st.session_state.pop("picker", None)
elif resuming:
    # The form was submitted in the previous run; continue the agent now.
    answer = resuming["answer"]
elif not question:
    with view.container():
        if open_view == SNAPSHOT:
            outcome = render_snapshot_view(turns, thread_id)
        elif open_view == REPORT:
            outcome = render_report_view(turns, thread_id)
        else:
            outcome = render_ask_view(turns, thread_id, waiting)
    if outcome.new:
        st.query_params["c"] = new_thread_id()
        st.rerun()
    if outcome.answer is not None:
        # Draw the page again first, so the question box has the right words.
        st.session_state["resume"] = {"thread": thread_id, "answer": outcome.answer}
        st.rerun()
    # A button in the view (such as "Save to reports folder") sends a
    # question, just as typing it would.
    question = outcome.question

# The assistant, at the bottom right of every view: a small chat of its own
# for a quick question in between. It is given the newest report, or else
# the newest answer, and what is asked there stays out of the conversation.
answered = [turn.answer for turn in turns if turn.answer is not None]
# It is named after the report, or else after the first question.
assistant_title = (report_title(reports[-1].report) if reports
                   else short_title(turns[0].question) if turns else "")
render_assistant(
    thread_id, title=assistant_title[:1].upper() + assistant_title[1:],
    context=(reports[-1].report if reports else answered[-1].text if answered else ""),
    get_model=lambda: get_side_model(settings["model_name"]),
    on_used=lambda used: usage_log.record(runtime.store, user_id, usage_log.ASSISTANT, usage=used))

# A message that is empty or far too long is turned back here, before it
# costs anything.
if question:
    problem = check_question(question)
    if problem:
        st.warning(problem)
        usage_log.record(runtime.store, user_id, usage_log.TURNED_AWAY, thread=thread_id)
        question = None

# Each finished answer, and each failure, leaves a line in the usage log
# (agent/usage_log.py) for the Dashboard and Admin pages.
def log_answer(ran: dict) -> None:
    if pending_pause(runtime.agent, thread_id) is not None:
        return                  # counted once the report is finished
    newest = to_turns(to_blocks(load_messages(runtime.agent, thread_id)))
    block = newest[-1].answer if newest else None
    if block is None:
        return
    usage_log.record(runtime.store, user_id, usage_log.ANSWERED, seconds=ran["seconds"],
                     usage=block.usage, tools=ran["tools"], report=bool(block.report),
                     sources=len(block.sources), thread=thread_id)


def log_error(tools: list[str], seconds: float, message: str) -> None:
    usage_log.record(runtime.store, user_id, usage_log.ERROR, seconds=seconds, tools=tools,
                     error=message, thread=thread_id)


# Run the agent in the live view, then draw the page again from the saved
# state: that shows the answer, or the next approval form.
if answer is not None:
    latest = turns[-1]
    view.empty()
    with live.container():
        ran = run_live(runtime.agent, thread_id, context, title=latest.question,
                       turn_index=len(turns) - 1, answer=answer,
                       earlier_steps=latest.answer.activity if latest.answer else [], turns=turns,
                       on_error=log_error)
        log_answer(ran)
    # A deployed copy keeps a copy of the memory file after every answer.
    backup_memory()
    st.rerun()
elif question and not waiting:
    if account:
        # The conversation belongs to whoever asks its first question.
        claim_conversation(runtime.store, thread_id, user_id)
    view.empty()
    with live.container():
        ran = run_live(runtime.agent, thread_id, context, title=question,
                       turn_index=len(turns), question=question, turns=turns, on_error=log_error)
        log_answer(ran)
    # A deployed copy keeps a copy of the memory file after every answer.
    backup_memory()
    st.rerun()
