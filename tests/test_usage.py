"""Tests for token usage and cost.

The model service reports, for every call, how many tokens were read and
written and what the call cost. These tests run real chat turns (and, below,
a real report) through the agent with fake models that report figures the
test chooses, then read the result the way the app does: from the saved
conversation, as the blocks the page displays.

Every expected number is worked out by hand in the test.
"""

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agent import usage as usage_module
from agent.agent import assemble_agent, resume_steps, stream_steps
from agent.approval import review_answer
from agent.memory import UserContext
from agent.session import load_messages, to_blocks
from tests.test_source_check import fake_tools
from tests.test_styles import ListeningModel, write_report


def reply(text: str, read: int, written: int, cost: float | None,
          tool: str | None = None) -> AIMessage:
    """What the model sends back, with the figures the service reports for
    the call: tokens read, tokens written, and the cost in dollars (None if
    the service gave no cost)."""
    calls = [{"name": tool, "id": f"call-{read}", "args": {"subject": "HelloFresh"}}] if tool else []
    usage = {"prompt_tokens": read, "completion_tokens": written, "total_tokens": read + written}
    if cost is not None:
        usage["cost"] = cost
    return AIMessage(text, tool_calls=calls,
                     usage_metadata={"input_tokens": read, "output_tokens": written,
                                     "total_tokens": read + written},
                     response_metadata={"token_usage": usage})


def chat(turns: list[list[AIMessage]], tools: list | None = None):
    """Ask one question per list of replies, in one conversation. Returns
    the blocks the page would display."""
    replies = [message for turn in turns for message in turn]
    agent = assemble_agent(ListeningModel(messages=iter(replies)), [], tools=tools or [],
                           checkpointer=InMemorySaver(), store=InMemoryStore())
    for number, _ in enumerate(turns):
        list(stream_steps(agent, f"Question {number + 1}", "thread-1",
                          context=UserContext(user_id="tester")))
    return to_blocks(load_messages(agent, "thread-1"))


# --- a chat answer -----------------------------------------------------------------------------

def test_an_answer_shows_the_tokens_and_cost_the_service_reported():
    blocks = chat([[reply("HelloFresh employs 11,447 people.", read=1200, written=40, cost=0.0005)]])

    usage = blocks[-1].usage
    assert (usage.calls, usage.input_tokens, usage.output_tokens) == (1, 1200, 40)
    assert usage.total_tokens == 1240
    assert usage.cost == pytest.approx(0.0005)


def test_every_model_call_made_for_one_question_is_added_up():
    # The model first asks for a tool, then writes the answer: two calls.
    figures = ("get_company_financials", "Employees: 11447")
    blocks = chat([[reply("", read=1000, written=20, cost=0.0004, tool=figures[0]),
                    reply("HelloFresh employs 11,447 people.", read=1300, written=45, cost=0.0006)]],
                  tools=fake_tools([figures]))

    usage = blocks[-1].usage
    assert usage.calls == 2
    assert (usage.input_tokens, usage.output_tokens) == (2300, 65)      # 1000+1300, 20+45
    assert usage.cost == pytest.approx(0.0010)                          # 0.0004+0.0006


def test_each_question_keeps_its_own_figures():
    blocks = chat([[reply("First answer.", read=500, written=10, cost=0.0002)],
                   [reply("Second answer.", read=900, written=30, cost=0.0004)]])

    answers = [block for block in blocks if block.role == "assistant"]
    assert [a.usage.total_tokens for a in answers] == [510, 930]
    assert [a.usage.cost for a in answers] == [pytest.approx(0.0002), pytest.approx(0.0004)]


def test_a_question_has_no_usage_of_its_own():
    blocks = chat([[reply("An answer.", read=500, written=10, cost=0.0002)]])

    assert blocks[0].role == "user"
    assert blocks[0].usage.calls == 0


# --- a call the service gave no cost for -------------------------------------------------------
# The app never makes up a price. A call without a reported cost counts its
# tokens, and is remembered as unpriced so the page can say so.

def test_a_call_without_a_reported_cost_counts_its_tokens_but_no_price():
    blocks = chat([[reply("An answer.", read=800, written=20, cost=None)]])

    usage = blocks[-1].usage
    assert usage.total_tokens == 820
    assert usage.cost == 0.0
    assert (usage.calls, usage.priced_calls) == (1, 0)


def test_priced_and_unpriced_calls_are_told_apart():
    figures = ("get_company_financials", "Employees: 11447")
    blocks = chat([[reply("", read=1000, written=20, cost=None, tool=figures[0]),
                    reply("An answer.", read=1300, written=45, cost=0.0006)]],
                  tools=fake_tools([figures]))

    usage = blocks[-1].usage
    assert (usage.calls, usage.priced_calls) == (2, 1)
    assert usage.cost == pytest.approx(0.0006)


def test_a_cost_of_exactly_zero_is_a_price_not_a_missing_one():
    # Some models are free. Zero dollars was reported; nothing is unknown.
    blocks = chat([[reply("An answer.", read=800, written=20, cost=0.0)]])

    assert (blocks[-1].usage.calls, blocks[-1].usage.priced_calls) == (1, 1)


# --- a report ----------------------------------------------------------------------------------
# A report is written by a workflow that asks its model many separate
# questions. None of those calls is a message in the conversation, so the
# workflow has to count them itself. In these tests every one of its calls
# uses 100 tokens read, 10 written and costs $0.0001, and the chat model's
# own call (asking for the report) uses 2,000 read, 30 written and $0.001.

def asks_for_report() -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "create_market_report", "id": "r1",
                                      "args": {"product": "meal kits", "country": "Germany"}}],
                     usage_metadata={"input_tokens": 2000, "output_tokens": 30, "total_tokens": 2030},
                     response_metadata={"token_usage": {"cost": 0.001}})


def workflow_call() -> None:
    """The workflow's model reporting one call."""
    usage_module.record(reply("", read=100, written=10, cost=0.0001))


def report_usage(review: bool = False, then=None, expect_report: bool = True):
    """Write a report and return (the usage shown with it, how many
    questions the workflow asked its model, the block that is displayed)."""
    context = UserContext(user_id="tester", review_competitors=review)
    heard, saved, _ = write_report(context, asks_for_report=asks_for_report(),
                                   model_call=workflow_call, then=then,
                                   expect_report=expect_report)
    asked = sum(len(questions) for questions in heard.values())
    block = to_blocks(saved)[-1]
    return block.usage, asked, block


def test_a_report_counts_every_question_the_workflow_asked_its_model():
    used, asked, block = report_usage()

    assert block.report                                   # a report was written
    assert asked >= 5                                     # brief, candidates, verdict, ..., SWOT
    assert used.calls == asked + 1                        # plus the chat model's own call
    assert used.input_tokens == asked * 100 + 2000
    assert used.output_tokens == asked * 10 + 30
    assert used.cost == pytest.approx(asked * 0.0001 + 0.001)
    assert used.priced_calls == used.calls


def test_what_was_spent_before_the_competitor_review_is_not_lost_by_the_pause():
    asked_at_the_pause = []

    def approve(agent):
        asked_at_the_pause.append(calls_so_far[0])
        list(resume_steps(agent, review_answer("approve"), "thread-report",
                          context=UserContext(user_id="tester", review_competitors=True)))

    calls_so_far = [0]
    original = workflow_call

    def counting_call():
        calls_so_far[0] += 1
        original()

    context = UserContext(user_id="tester", review_competitors=True)
    heard, saved, _ = write_report(context, asks_for_report=asks_for_report(),
                                   model_call=counting_call, then=approve)
    asked = sum(len(questions) for questions in heard.values())
    used = to_blocks(saved)[-1].usage

    assert 0 < asked_at_the_pause[0] < asked              # the model was asked on both sides
    assert used.calls == asked + 1
    assert used.cost == pytest.approx(asked * 0.0001 + 0.001)


def test_a_report_cancelled_at_the_review_still_shows_what_it_cost_up_to_then():
    def cancel(agent):
        list(resume_steps(agent, review_answer("cancel"), "thread-report",
                          context=UserContext(user_id="tester", review_competitors=True)))

    used, asked, block = report_usage(review=True, then=cancel, expect_report=False)

    assert not block.report
    assert "cancelled" in block.text
    assert asked >= 3                                     # brief, candidates, at least one verdict
    assert used.calls == asked + 1
    assert used.cost == pytest.approx(asked * 0.0001 + 0.001)


# --- the workflow's own way of asking ----------------------------------------------------------
# The real workflow asks through ask_with_retry, which repeats a question
# when the answer has the wrong shape. A repeated question is a second call
# and costs money too.

class Shaped:
    """Stands in for a model that answers in a fixed shape. Each reply is
    (the answer or None, the figures of the call, an error or None), in the
    layout the real one returns."""

    def __init__(self, replies):
        self.replies = list(replies)

    def invoke(self, messages):
        return self.replies.pop(0)


def shaped_reply(parsed, read, written, cost, error=None) -> dict:
    return {"raw": reply("", read=read, written=written, cost=cost),
            "parsed": parsed, "parsing_error": error}


def test_a_question_that_had_to_be_repeated_is_counted_twice():
    from langchain_core.exceptions import OutputParserException

    from agent.report.deps import ask_with_retry

    model = Shaped([shaped_reply(None, 400, 15, 0.0002, OutputParserException("missing field")),
                    shaped_reply("the answer", 450, 20, 0.0003)])

    with usage_module.collecting() as calls:
        answer = ask_with_retry(model, "Judge.", "Material")

    assert answer == "the answer"
    used = usage_module.total(calls)
    assert (used.calls, used.input_tokens, used.output_tokens) == (2, 850, 35)
    assert used.cost == pytest.approx(0.0005)


def test_a_call_made_outside_any_report_step_is_simply_not_collected():
    # record() must be safe to call anywhere, such as from a test or a tool.
    usage_module.record(reply("", read=100, written=10, cost=0.0001))

    with usage_module.collecting() as calls:
        pass

    assert calls == []


# --- the background call -----------------------------------------------------------------------
# Before the agent answers, a small separate model call reads the user's
# message for lasting facts (their country, their industry). It is paid for
# like any other call, so it is counted with the question it belongs to.

def chat_with_background_call(replies: list[AIMessage]):
    def extract(text: str) -> dict:
        # The fact extractor's model reporting its one call.
        usage_module.record(reply("", read=300, written=12, cost=0.00008))
        return {}

    model = ListeningModel(messages=iter(replies))
    agent = assemble_agent(model, [], tools=[], checkpointer=InMemorySaver(),
                           store=InMemoryStore(), extract_facts=extract)
    list(stream_steps(agent, "I sell oat milk in Germany.", "thread-1",
                      context=UserContext(user_id="tester")))
    return to_blocks(load_messages(agent, "thread-1")), model


def test_the_background_call_is_counted_with_the_answer_to_that_question():
    blocks, _ = chat_with_background_call([reply("Noted.", read=1200, written=40, cost=0.0005)])

    used = blocks[-1].usage
    assert used.calls == 2                                # the answer and the background call
    assert (used.input_tokens, used.output_tokens) == (1500, 52)       # 1200+300, 40+12
    assert used.cost == pytest.approx(0.00058)                         # 0.0005+0.00008


def test_counting_the_background_call_does_not_change_the_conversation():
    blocks, model = chat_with_background_call([reply("Noted.", read=1200, written=40, cost=0.0005)])

    assert [block.role for block in blocks] == ["user", "assistant"]
    assert blocks[0].text == "I sell oat milk in Germany."
    assert blocks[0].usage.calls == 0                     # shown with the answer, not the question
    # The model was sent the user's message once, unchanged.
    sent = [m.content for m in model.received[-1] if m.type == "human"]
    assert sent == ["I sell oat milk in Germany."]


def test_the_real_fact_extractor_reports_its_call():
    from agent.memory import ProfileFacts, make_fact_extractor

    class Model:
        """Stands in for a chat model that answers in a fixed shape."""

        def with_structured_output(self, schema, **options):
            assert options.get("include_raw") is True, "the raw reply is needed for its figures"
            return Shaped([shaped_reply(ProfileFacts(region="Germany"), 300, 12, 0.00008)])

    extract = make_fact_extractor(Model())

    with usage_module.collecting() as calls:
        facts = extract("I sell oat milk in Germany.")

    assert facts == {"region": "Germany"}
    used = usage_module.total(calls)
    assert (used.calls, used.total_tokens) == (1, 312)
    assert used.cost == pytest.approx(0.00008)


# --- how it is worded --------------------------------------------------------------------------

def used(calls=1, read=0, written=0, cost=0.0, priced=None):
    from agent.usage import Usage
    return Usage(calls, read, written, cost, calls if priced is None else priced)


def test_the_tokens_and_the_cost_in_dollars_are_worded_separately():
    spent = used(read=1200, written=40, cost=0.0005)

    assert usage_module.tokens_text(spent) == "1,240 tokens"
    assert usage_module.cost_text(spent) == "$0.0005"


def test_a_small_cost_keeps_enough_digits_to_mean_something():
    costs = {0.00042: "$0.00042", 0.0005: "$0.0005", 0.001: "$0.001", 0.012: "$0.012",
             0.25: "$0.25", 0.5: "$0.50", 1.5: "$1.50", 12.345: "$12.35"}

    assert {cost: usage_module.format_cost(cost) for cost in costs} == costs


def test_a_free_call_is_shown_as_zero_dollars():
    assert usage_module.cost_text(used(read=800, written=20, cost=0.0)) == "$0"


def test_no_price_is_shown_when_the_service_reported_none():
    spent = used(read=800, written=20, priced=0)

    assert usage_module.cost_text(spent) == "not reported"
    assert usage_module.cost_note(spent) == ""


def test_a_cost_that_misses_some_calls_says_so():
    spent = used(calls=2, read=2300, written=65, cost=0.0006, priced=1)

    assert usage_module.cost_text(spent) == "$0.0006"
    assert usage_module.cost_note(spent) == "1 of 2 calls had no reported cost."


def test_a_complete_cost_needs_no_note():
    assert usage_module.cost_note(used(read=1200, written=40, cost=0.0005)) == ""


def test_nothing_is_shown_when_no_model_was_called():
    assert usage_module.tokens_text(used(calls=0)) == ""
    assert usage_module.cost_text(used(calls=0)) == ""


def test_the_details_break_the_figures_down_and_say_what_is_left_out():
    details = usage_module.details(used(calls=3, read=2300, written=65, cost=0.001))

    assert "3 model calls" in details
    assert "2,300 tokens read" in details
    assert "65 tokens written" in details
    assert "Web searches are billed separately and are not included." in details


def test_one_call_is_not_called_calls():
    assert "1 model call." in usage_module.details(used(calls=1, read=10, written=5, cost=0.0001))


# --- a report written before costs were recorded -----------------------------------------------

def test_an_older_report_shows_only_its_chat_part_and_says_so():
    from langchain_core.messages import HumanMessage, ToolMessage

    old_report = ToolMessage("# Market research report: oat milk in Germany\n\n## 1. Market overview",
                             tool_call_id="r1", name="create_market_report",
                             artifact={"problems": [], "log": []})     # no "usage" in it
    blocks = to_blocks([HumanMessage("A report please"), asks_for_report(), old_report])

    assert blocks[-1].usage.calls == 1                    # only the chat model's own call
    assert blocks[-1].usage_is_partial
    assert usage_module.cost_text(blocks[-1].usage) == "$0.001"
    assert usage_module.cost_note(blocks[-1].usage, partial=True) == \
        "The report's own calls were not recorded."


def test_a_new_report_is_not_marked_as_partial():
    _, _, block = report_usage()

    assert not block.usage_is_partial


# --- on the page ---------------------------------------------------------------------------------

from tests.test_app import make_runtime, page  # noqa: E402,F401  (page is a fixture)


def open_app(page, tmp_path, replies: list[AIMessage]):
    model = ListeningModel(messages=iter(replies))
    return page(runtime=make_runtime(tmp_path, [], model=model))


def notes(part) -> list[str]:
    """The small grey lines in a part of the page."""
    return [note.value for note in part.caption]


def pills(part) -> list[str]:
    """The cost pills in a part of the page, as HTML."""
    return [element.proto.body for element in part.get("html")
            if 'class="gw-cost-pill"' in element.proto.body]


def test_the_cost_of_an_answer_is_shown_in_a_pill_above_the_steps(page, tmp_path):
    app = open_app(page, tmp_path, [reply("An answer.", read=1200, written=40, cost=0.0005)])

    app.chat_input[0].set_value("How big is the oat milk market?").run()

    assert not app.exception
    [pill] = pills(app)
    assert "LLM cost" in pill and "$0.0005" in pill
    # The tokens are on the line under "Done".
    assert any("1,240 tokens" in note for note in notes(app))


def test_the_pill_shows_the_cost_of_the_answer_on_screen_not_of_the_conversation(page, tmp_path):
    app = open_app(page, tmp_path, [reply("First answer.", read=500, written=10, cost=0.0002),
                                    reply("Second answer.", read=900, written=30, cost=0.0004)])
    app.chat_input[0].set_value("First question").run()

    app.chat_input[0].set_value("Second question").run()

    [pill] = pills(app)
    assert "$0.0004" in pill
    assert any("930 tokens" in note for note in notes(app))


def test_the_sidebar_shows_no_cost(page, tmp_path):
    app = open_app(page, tmp_path, [reply("An answer.", read=1200, written=40, cost=0.0005)])

    app.chat_input[0].set_value("How big is the oat milk market?").run()

    assert not pills(app.sidebar)
    assert not any("tokens" in note or "$" in note for note in notes(app.sidebar))


def test_an_empty_conversation_shows_no_cost_anywhere(page, tmp_path):
    app = open_app(page, tmp_path, [])

    assert not pills(app)
    assert not any("tokens" in note for note in notes(app) + notes(app.sidebar))


# --- a question that never got an answer -------------------------------------------------------

def test_what_was_spent_on_a_question_without_an_answer_is_still_in_the_total():
    # The user stopped the first question before the model replied. Its
    # background call had already been made and paid for.
    from langchain_core.messages import HumanMessage

    spent_reading = {"calls": 1, "input_tokens": 300, "output_tokens": 12,
                     "cost": 0.00008, "priced_calls": 1}
    first = HumanMessage("A question that was stopped",
                         response_metadata={"background_usage": spent_reading})
    second = HumanMessage("A second question",
                          response_metadata={"background_usage": spent_reading})
    blocks = to_blocks([first, second,
                        reply("An answer.", read=1200, written=40, cost=0.0005)])

    total_spent = sum((block.usage for block in blocks), usage_module.Usage())
    assert total_spent.calls == 3                         # two background calls and one answer
    assert total_spent.cost == pytest.approx(0.00066)     # 0.00008 + 0.00008 + 0.0005
    # The answer shows only what its own question used.
    assert blocks[-1].usage.calls == 2
    assert blocks[-1].usage.cost == pytest.approx(0.00058)


def test_the_same_holds_when_the_stopped_question_is_the_last_one():
    from langchain_core.messages import HumanMessage

    spent_reading = {"calls": 1, "input_tokens": 300, "output_tokens": 12,
                     "cost": 0.00008, "priced_calls": 1}
    blocks = to_blocks([HumanMessage("A question that was stopped",
                                     response_metadata={"background_usage": spent_reading})])

    assert len(blocks) == 1
    assert blocks[0].usage.cost == pytest.approx(0.00008)


def test_the_page_says_so_when_an_older_report_misses_its_own_calls(page, tmp_path):
    from langchain_core.messages import ToolMessage
    from streamlit.testing.v1 import AppTest

    from tests.test_app import APP

    runtime = make_runtime(tmp_path, [])
    old_report = ToolMessage("# Market research report: oat milk in Germany\n\n## 1. Market overview",
                             tool_call_id="r1", name="create_market_report",
                             artifact={"problems": [], "log": []})     # written before costs were recorded
    runtime.agent.update_state({"configurable": {"thread_id": "old"}}, {"messages": [
        {"role": "user", "content": "A report please"}, asks_for_report(), old_report]},
        as_node="tools")
    page(runtime=runtime)                                 # puts the fake agent in place

    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["c"] = "old"
    app.run()

    assert not app.exception
    [pill] = pills(app)
    assert "$0.001" in pill
    assert any("The report's own calls were not recorded." in note for note in notes(app))
