"""Tests for tracing with LangSmith.

Tracing sends every model and tool call of a run to LangSmith, where it can
be read step by step. It is on only when a key is set. The tests never
send a trace: tests/conftest.py switches tracing off before anything runs.
"""

import os

from langchain_core.messages import AIMessage
from langchain_core.tracers.context import collect_runs
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agent.agent import assemble_agent, stream_steps
from agent.memory import UserContext
from agent.side_assistant import ask
from agent.tracing import configure_tracing, tracing_is_on
from tests.test_app import page  # noqa: F401  (page is a fixture)
from tests.test_assistant import RecordingModel
from tests.test_styles import listening


# --- when tracing is on ----------------------------------------------------------------------------

def test_without_a_key_tracing_is_off_whatever_else_is_set():
    env = {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": ""}

    assert configure_tracing(env) is False
    assert env["LANGSMITH_TRACING"] == "false"         # so nothing tries, and warns, without a key


def test_with_a_key_tracing_is_on_and_goes_to_the_local_project():
    env = {"LANGSMITH_API_KEY": "a-key"}

    assert configure_tracing(env) is True
    assert env["LANGSMITH_TRACING"] == "true"
    assert env["LANGSMITH_PROJECT"] == "markavi-local"


def test_a_deployed_copy_traces_to_a_project_of_its_own():
    env = {"LANGSMITH_API_KEY": "a-key", "K_SERVICE": "markavi"}     # set by Cloud Run

    configure_tracing(env)

    assert env["LANGSMITH_PROJECT"] == "markavi-live"


def test_a_project_named_in_the_settings_is_kept():
    env = {"LANGSMITH_API_KEY": "a-key", "LANGSMITH_PROJECT": "my-own"}

    configure_tracing(env)

    assert env["LANGSMITH_PROJECT"] == "my-own"


def test_tracing_can_be_switched_off_with_a_key_in_place():
    env = {"LANGSMITH_API_KEY": "a-key", "LANGSMITH_TRACING": "false"}

    assert configure_tracing(env) is False
    assert tracing_is_on(env) is False


def test_the_tests_themselves_never_trace():
    assert os.environ.get("LANGSMITH_TRACING") == "false"
    assert tracing_is_on() is False


# --- what a trace is labelled with ---------------------------------------------------------------

def chat_run(context: UserContext):
    agent = assemble_agent(listening(), [], tools=[], checkpointer=InMemorySaver(),
                           store=InMemoryStore(), extract_facts=lambda message: {})
    with collect_runs() as seen:
        list(stream_steps(agent, "How big is HelloFresh?", "thread-7", context=context))
    # The run of the whole turn; the model's own call is listed as well.
    return next(run for run in seen.traced_runs if run.name == "Markavi chat")


def test_a_chat_run_is_named_and_labelled_with_its_conversation():
    run = chat_run(UserContext(user_id="u-anna", model_name="openai/gpt-4.1-mini", language="de"))

    assert run.name == "Markavi chat"
    assert "chat" in run.tags
    assert run.metadata["thread_id"] == "thread-7"            # LangSmith groups a conversation by this
    assert run.metadata["user_id"] == "u-anna"
    assert run.metadata["model"] == "openai/gpt-4.1-mini"
    assert run.metadata["language"] == "de"


def test_a_trace_is_labelled_with_the_account_id_and_nothing_personal():
    run = chat_run(UserContext(user_id="u-anna"))

    ours = {key for key in run.metadata if not key.startswith(("ls_", "lc_", "langgraph_", "checkpoint"))}
    assert ours <= {"thread_id", "user_id", "model", "language", "revision_id"}


def test_the_assistant_names_its_calls_too():
    model = RecordingModel("ok")

    ask(model, "What is CAGR?", history=[], context="")

    assert model.configs[0]["run_name"] == "Markavi assistant"
    assert model.configs[0]["tags"] == ["assistant"]


# --- on the page ---------------------------------------------------------------------------------

def test_the_help_panel_says_that_tracing_is_off(page):  # noqa: F811
    app = page()

    assert "Tracing is off." in [c.value for c in app.sidebar.caption]


def test_the_help_panel_says_when_runs_are_traced(page):  # noqa: F811
    from unittest.mock import patch

    with patch("ui.sidebar.tracing_is_on", lambda: True):
        app = page()

    assert "Runs are traced with LangSmith for debugging." in [c.value for c in app.sidebar.caption]


def test_a_fake_answer_still_works_with_tracing_code_in_place(page):  # noqa: F811
    app = page([AIMessage("An answer.")])

    app.chat_input[0].set_value("How big is HelloFresh?").run()

    assert not app.exception
