"""Tests for sending a rating to LangSmith, onto the trace of its answer.

Each answer is run with a known run id, kept with the conversation and the
answer's place in it. A rating is then sent to that run as feedback named
"user_rating" (1 = thumbs up, 0 = thumbs down), with the reasons and the
comment. Rating again replaces it; taking the rating back removes it.
Nothing is sent when tracing is off, and a failure never reaches the user.
"""

from unittest.mock import patch
from uuid import UUID

from langchain_core.messages import AIMessage
from langgraph.store.memory import InMemoryStore

from agent.agent import run_config
from agent.feedback import DOWN, UP, remember_run, run_of
from agent.memory import UserContext
from agent.trace_feedback import KEY, feedback_id, send_rating
from tests.test_app import page  # noqa: F401  (page is a fixture)
from tests.test_ask_view import ask
from tests.test_feedback import thumbs

RUN = "3f1c2a9e-0d8b-4c47-9a51-6f1f0f6a2b10"
TRACING = {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "test-key-not-real"}


class FakeClient:
    def __init__(self, fail: bool = False):
        self.calls, self.fail = [], fail

    def create_feedback(self, run_id, key, **kwargs):
        if self.fail:
            raise ConnectionError("LangSmith is down")
        self.calls.append(("create", str(run_id), key, kwargs))

    def delete_feedback(self, feedback_id):
        self.calls.append(("delete", str(feedback_id)))


# --- the run id ----------------------------------------------------------------------------------

def test_a_run_is_given_the_run_id_chosen_for_it():
    config = run_config("t1", UserContext(user_id="u-anna"), run_id=RUN)

    assert config["run_id"] == UUID(RUN)
    assert config["configurable"] == {"thread_id": "t1"}


def test_without_a_run_id_langchain_chooses_one():
    assert "run_id" not in run_config("t1", UserContext(user_id="u-anna"))


def test_the_run_of_an_answer_is_remembered_per_account():
    store = InMemoryStore()

    remember_run(store, "u-anna", "t1", 0, RUN)

    assert run_of(store, "u-anna", "t1", 0) == RUN
    assert run_of(store, "u-ben", "t1", 0) is None


# --- sending -------------------------------------------------------------------------------------

def test_a_thumbs_down_is_sent_with_its_reasons_and_comment():
    client = FakeClient()

    sent = send_rating(RUN, DOWN, ["too_long"], "Top 3 only.", client=client, env=TRACING)

    assert sent
    _, run_id, key, details = client.calls[-1]
    assert (run_id, key) == (RUN, KEY)
    assert (details["score"], details["value"], details["comment"]) == (0, "too_long", "Top 3 only.")
    assert details["feedback_id"] == feedback_id(RUN)


def test_rating_again_replaces_the_feedback_and_taking_it_back_removes_it():
    client = FakeClient()

    send_rating(RUN, UP, [], "", client=client, env=TRACING)
    send_rating(RUN, None, [], "", client=client, env=TRACING)

    assert [call[0] for call in client.calls] == ["delete", "create", "delete"]
    assert {call[1] for call in client.calls if call[0] == "delete"} == {str(feedback_id(RUN))}


def test_nothing_is_sent_when_tracing_is_off_or_the_run_is_unknown():
    client = FakeClient()

    assert not send_rating(RUN, UP, [], "", client=client, env={"LANGSMITH_TRACING": "false"})
    assert not send_rating(None, UP, [], "", client=client, env=TRACING)
    assert client.calls == []


def test_a_failure_to_send_is_kept_from_the_user():
    assert not send_rating(RUN, UP, [], "", client=FakeClient(fail=True), env=TRACING)


# --- on the page ---------------------------------------------------------------------------------

def test_rating_an_answer_sends_it_to_the_run_of_that_answer(page):  # noqa: F811
    sent = []
    with patch("ui.feedback.send_in_background", lambda *args: sent.append(args)):
        app = ask(page([AIMessage("An answer.")]), "A question")
        run = run_of(app.runtime.store, "default-user", app.query_params["c"], 0)

        thumbs(app, 0).set_value(UP).run()

    assert run is not None
    assert sent[-1] == (run, UP, [], "")
