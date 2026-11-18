"""Tests for the assistant: a small chat at the bottom right of every view,
for a quick question in between.

It is separate from the conversation: what is asked there is not added to
the conversation, it searches nothing, and it answers from the report that
is open. The model is a fake one that records what it was sent.
"""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.session import load_messages
from agent.side_assistant import HISTORY_MAX_MESSAGES, REPORT_MAX_CHARS, ask
from tests.test_app import button, make_runtime, page  # noqa: F401  (page is a fixture)
from tests.test_snapshot import with_snapshot


class RecordingModel:
    """A model that answers with the given replies and keeps what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.sent = []

    def invoke(self, messages):
        self.sent.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, AIMessage) else AIMessage(reply)


def priced(text, cost):
    return AIMessage(text, usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                     response_metadata={"token_usage": {"cost": cost}})


# --- one question to the model -------------------------------------------------------------------

def test_the_model_gets_the_rules_the_open_report_and_the_question():
    model = RecordingModel("CAGR is the yearly growth rate.")

    text, used = ask(model, "What is CAGR?", history=[], context="# Oat milk in Germany\n\nA fact.")

    rules, question = model.sent[0]
    assert isinstance(rules, SystemMessage) and "# Oat milk in Germany" in rules.content
    assert question == HumanMessage("What is CAGR?")
    assert text == "CAGR is the yearly growth rate."
    assert used.calls == 0                                   # the fake reply reports no usage


def test_without_an_open_report_the_rules_say_so():
    model = RecordingModel("Open a report first.")

    ask(model, "Who are the competitors?", history=[], context="")

    assert "No report or answer is open." in model.sent[0][0].content


def test_the_rules_keep_it_from_inventing_figures():
    model = RecordingModel("ok")

    ask(model, "How big is the market?", history=[], context="")

    rules = model.sent[0][0].content
    assert "cannot search the web" in rules and "Never state a market figure" in rules


def test_earlier_questions_and_answers_are_sent_in_order():
    model = RecordingModel("And a second answer.")
    history = [{"role": "user", "text": "First?"}, {"role": "assistant", "text": "First answer."}]

    ask(model, "Second?", history=history, context="")

    assert model.sent[0][1:] == [HumanMessage("First?"), AIMessage("First answer."),
                                 HumanMessage("Second?")]


def test_only_the_newest_part_of_a_long_chat_is_sent():
    model = RecordingModel("ok")
    history = [{"role": "user", "text": f"q{number}"} for number in range(30)]

    ask(model, "Now?", history=history, context="")

    sent = model.sent[0]
    assert len(sent) == 1 + HISTORY_MAX_MESSAGES + 1 == 12
    assert sent[1] == HumanMessage("q20")


def test_a_very_long_report_is_cut_before_it_is_sent():
    model = RecordingModel("ok")

    ask(model, "Summarise", history=[], context="§" * 50_000)

    assert model.sent[0][0].content.count("§") == REPORT_MAX_CHARS == 24_000


def test_the_cost_of_the_answer_is_returned():
    _, used = ask(RecordingModel(priced("ok", 0.001)), "q", history=[], context="")

    assert (used.calls, used.cost) == (1, 0.001)


# --- on the page ---------------------------------------------------------------------------------

@pytest.fixture
def helper():
    """Gives the page a fake model for the assistant. Returns a function
    that sets its replies and returns the model."""
    model = RecordingModel()
    with patch("ui.runtime.get_side_model", lambda *args, **kwargs: model):
        def with_replies(*replies):
            model.replies = list(replies)
            return model
        yield with_replies


def bubbles(app) -> list[str]:
    return [element.proto.body for element in app.get("html")
            if 'class="gw-helper-question"' in element.proto.body]


def answers(app) -> list[str]:
    return [message.markdown[0].value for message in app.chat_message]


def helper_box(app):
    return next((box for box in app.chat_input if box.key == "assistant_question"), None)


def opened(app):
    button(app, "assistant_open").click().run()
    return app


def test_the_assistant_is_closed_at_first_on_the_start_screen(page, helper):  # noqa: F811
    app = page()

    assert button(app, "assistant_open").label == "Assistant"
    assert helper_box(app) is None


def test_the_button_is_there_in_every_view(page, tmp_path, helper):  # noqa: F811
    app = with_snapshot(page, tmp_path)

    for view in ("view_snapshot", "view_ask", "view_report"):
        button(app, view).click().run()
        assert not app.exception
        assert button(app, "assistant_open") is not None, view


def test_opening_it_shows_a_question_box_about_the_open_report(page, tmp_path, helper):  # noqa: F811
    app = opened(with_snapshot(page, tmp_path))

    assert not app.exception
    assert helper_box(app).placeholder == "Ask something about this report…"
    head = next(e.proto.body for e in app.get("html") if 'class="gw-helper-head"' in e.proto.body)
    assert "Assistant · Oat milk in Germany" in head
    assert "Only about this conversation" in head


def test_on_the_start_screen_it_takes_general_questions(page, helper):  # noqa: F811
    app = opened(page())

    assert helper_box(app).placeholder == "Ask a quick question…"


def test_a_question_is_answered_in_the_panel_from_the_report(page, tmp_path, helper):  # noqa: F811
    model = helper(priced("It means **yearly** growth.", 0.001))
    app = opened(with_snapshot(page, tmp_path))

    helper_box(app).set_value("What is CAGR?").run()

    assert not app.exception
    assert len(bubbles(app)) == 1 and "What is CAGR?" in bubbles(app)[0]
    assert answers(app) == ["It means **yearly** growth."]
    assert "Market research report: oat milk in Germany" in model.sent[0][0].content
    assert "This chat: $0.001" in [c.value for c in app.caption]


def test_the_costs_of_a_chat_add_up(page, tmp_path, helper):  # noqa: F811
    helper(priced("One.", 0.001), priced("Two.", 0.002))
    app = opened(with_snapshot(page, tmp_path))

    helper_box(app).set_value("First?").run()
    helper_box(app).set_value("Second?").run()

    assert answers(app) == ["One.", "Two."]
    assert "This chat: $0.003" in [c.value for c in app.caption]


def test_a_question_there_is_not_added_to_the_conversation(page, tmp_path, helper):  # noqa: F811
    helper("An answer.")
    runtime = make_runtime(tmp_path, [])
    app = opened(with_snapshot(page, tmp_path, runtime=runtime))
    before = len(load_messages(runtime.agent, "snap"))

    helper_box(app).set_value("A quick one?").run()
    button(app, "view_ask").click().run()

    assert before == len(load_messages(runtime.agent, "snap")) == 3
    asked = [e.proto.body for e in app.get("html") if 'class="gw-ask-question"' in e.proto.body]
    assert len(asked) == 1 and "A quick one?" not in asked[0]


def test_minimising_keeps_the_chat_and_new_chat_empties_it(page, tmp_path, helper):  # noqa: F811
    helper("An answer.")
    app = opened(with_snapshot(page, tmp_path))
    helper_box(app).set_value("A quick one?").run()

    button(app, "assistant_close").click().run()
    assert helper_box(app) is None
    opened(app)
    assert answers(app) == ["An answer."]

    button(app, "assistant_new").click().run()
    assert answers(app) == [] and bubbles(app) == []
    assert helper_box(app) is not None                       # still open, ready for a question


def test_it_stays_open_from_one_view_to_the_next(page, tmp_path, helper):  # noqa: F811
    helper("An answer.")
    app = opened(with_snapshot(page, tmp_path))
    helper_box(app).set_value("A quick one?").run()

    button(app, "view_report").click().run()

    assert answers(app) == ["An answer."]


def test_each_conversation_has_its_own_chat(page, tmp_path, helper):  # noqa: F811
    helper("An answer.")
    app = opened(with_snapshot(page, tmp_path))
    helper_box(app).set_value("A quick one?").run()

    button(app, "new_conversation").click().run()

    assert answers(app) == [] and bubbles(app) == []


def test_words_typed_there_are_shown_as_text_never_as_markup(page, tmp_path, helper):  # noqa: F811
    helper("An answer.")
    app = opened(with_snapshot(page, tmp_path))

    helper_box(app).set_value("<script>alert(1)</script>").run()

    assert "&lt;script&gt;" in bubbles(app)[0] and "<script>" not in bubbles(app)[0]


def test_the_question_box_takes_no_more_than_the_apps_limit(page, tmp_path, helper):  # noqa: F811
    app = opened(with_snapshot(page, tmp_path))

    assert helper_box(app).proto.max_chars == 2000


def test_a_failure_is_explained_and_the_chat_goes_on(page, tmp_path, helper):  # noqa: F811
    helper(RuntimeError("Request timed out"), "A later answer.")
    app = opened(with_snapshot(page, tmp_path))

    helper_box(app).set_value("First?").run()
    assert not app.exception
    assert answers(app) == ["The request took too long and was stopped. Try again."]

    helper_box(app).set_value("Second?").run()
    assert answers(app)[-1] == "A later answer."
