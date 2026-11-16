"""Tests for the logic behind the web app: turning saved messages into chat
bubbles and listing conversations. No Streamlit and no internet."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import memory, session
from agent.agent import assemble_agent, stream_steps

REPORT = "# Market research report: meal kits in Germany\n\n## 1. Market overview\n..."


def tool_call(name: str, args: dict, call_id: str = "1") -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "id": call_id, "args": args}])


# --- plain-language descriptions of what the agent did ------------------------------------

def test_tool_calls_are_described_in_plain_words():
    describe = session.describe_tool_call

    assert describe("web_search", {"query": "meal kits Germany"}) == \
        "Searched the web: meal kits Germany"
    assert describe("read_webpage", {"url": "https://prepmymeal.com"}) == \
        "Read the page https://prepmymeal.com"
    assert describe("get_demand_trend", {"term": "Kochbox", "country": "Germany"}) == \
        "Checked search interest for 'Kochbox' in Germany"
    assert describe("remember_preference", {"key": "business_idea", "value": "x"}) == \
        "Remembered your business idea"


def test_an_unknown_tool_still_gets_a_description():
    assert session.describe_tool_call("new_tool", {}) == "Used new_tool"


# --- messages -> chat bubbles ----------------------------------------------------------------

def test_a_question_and_answer_become_two_bubbles():
    blocks = session.to_blocks([HumanMessage("How big is HelloFresh?"),
                                AIMessage("It has 11,447 employees.")])

    assert [(b.role, b.text) for b in blocks] == [
        ("user", "How big is HelloFresh?"),
        ("assistant", "It has 11,447 employees."),
    ]


def test_the_agents_tool_use_is_folded_into_its_answer_bubble():
    blocks = session.to_blocks([
        HumanMessage("How big is HelloFresh?"),
        tool_call("get_company_financials", {"company": "HelloFresh"}),
        ToolMessage("Source used: Yahoo Finance\nRevenue: 6.2 billion EUR",
                    tool_call_id="1", name="get_company_financials"),
        AIMessage("Revenue is 6.2 billion EUR."),
    ])

    assert len(blocks) == 2
    assert blocks[1].text == "Revenue is 6.2 billion EUR."
    assert blocks[1].activity == ["Looked up company figures for HelloFresh"]


def test_raw_tool_results_are_not_shown_as_text():
    blocks = session.to_blocks([
        HumanMessage("Search"),
        tool_call("web_search", {"query": "x"}),
        ToolMessage("Source used: Tavily\n\n[1] Long raw result", tool_call_id="1",
                    name="web_search"),
        AIMessage("Here is the answer."),
    ])

    assert "Long raw result" not in blocks[1].text


def test_a_report_is_kept_separate_from_text_with_its_check_result():
    report_message = ToolMessage(
        REPORT, tool_call_id="1", name="create_market_report",
        artifact={"problems": [], "log": ["Report check: passed"]})

    blocks = session.to_blocks([
        HumanMessage("Give me a report"),
        tool_call("create_market_report", {"product": "meal kits", "country": "Germany"}),
        report_message,
    ])

    answer = blocks[1]
    assert answer.report == REPORT
    assert answer.text == ""
    assert answer.problems == []
    assert answer.activity == ["Started a report on meal kits in Germany",
                               "Workflow: Report check: passed"]


def test_a_report_with_issues_carries_them():
    blocks = session.to_blocks([ToolMessage(
        REPORT, tool_call_id="1", name="create_market_report",
        artifact={"problems": ["Section 4 is missing"], "log": []})])

    assert blocks[0].problems == ["Section 4 is missing"]


def test_a_short_message_from_the_report_tool_is_shown_as_text_not_as_a_report():
    # For example the question asked when no country was given.
    blocks = session.to_blocks([ToolMessage(
        "Which country should I look at?", tool_call_id="1", name="create_market_report")])

    assert blocks[0].text == "Which country should I look at?"
    assert blocks[0].report == ""
    assert blocks[0].problems is None


def test_each_user_message_starts_a_new_pair_of_bubbles():
    blocks = session.to_blocks([
        HumanMessage("First"), AIMessage("One"),
        HumanMessage("Second"), AIMessage("Two"),
    ])

    assert [b.text for b in blocks] == ["First", "One", "Second", "Two"]


def test_an_empty_conversation_has_no_bubbles():
    assert session.to_blocks([]) == []


# --- titles -----------------------------------------------------------------------------------

def test_the_title_is_the_first_question():
    assert session.title_from([HumanMessage("How big is HelloFresh?"),
                               AIMessage("Big.")]) == "How big is HelloFresh?"


def test_a_long_title_is_shortened_and_kept_on_one_line():
    title = session.title_from([HumanMessage(
        "Give me a market research report\nfor healthy meal delivery in Germany please")])

    assert title == "Give me a market research report for healt…"
    assert "\n" not in title


def test_a_conversation_without_a_question_has_no_title():
    assert session.title_from([AIMessage("Hello")]) == ""


def test_new_conversation_ids_are_short_and_different():
    first, second = session.new_thread_id(), session.new_thread_id()

    assert len(first) == 8
    assert first != second


# --- the list of conversations, on a real memory file -------------------------------------------

class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def agent_on_disk(tmp_path, replies: list):
    checkpointer, _ = memory.open_memory(tmp_path / "memory.db")
    model = ScriptedModel(messages=iter(replies))
    return assemble_agent(model, [], tools=[], checkpointer=checkpointer), checkpointer


def test_conversations_are_listed_newest_first_with_their_titles(tmp_path):
    agent, checkpointer = agent_on_disk(tmp_path, [AIMessage("One"), AIMessage("Two")])
    list(stream_steps(agent, "First question", "thread-a"))
    list(stream_steps(agent, "Second question", "thread-b"))

    conversations = session.list_conversations(agent, checkpointer)

    assert [(c.thread_id, c.title) for c in conversations] == [
        ("thread-b", "Second question"), ("thread-a", "First question")]


def test_using_an_older_conversation_moves_it_to_the_top(tmp_path):
    agent, checkpointer = agent_on_disk(
        tmp_path, [AIMessage("One"), AIMessage("Two"), AIMessage("Three")])
    list(stream_steps(agent, "First question", "thread-a"))
    list(stream_steps(agent, "Second question", "thread-b"))
    list(stream_steps(agent, "A follow-up", "thread-a"))

    assert session.thread_ids(checkpointer) == ["thread-a", "thread-b"]


def test_a_saved_conversation_can_be_loaded_again(tmp_path):
    agent, _ = agent_on_disk(tmp_path, [AIMessage("The answer")])
    list(stream_steps(agent, "The question", "thread-a"))

    blocks = session.to_blocks(session.load_messages(agent, "thread-a"))

    assert [(b.role, b.text) for b in blocks] == [("user", "The question"),
                                                   ("assistant", "The answer")]


def test_a_conversation_that_does_not_exist_loads_as_empty(tmp_path):
    agent, checkpointer = agent_on_disk(tmp_path, [])

    assert session.load_messages(agent, "never-used") == []
    assert session.list_conversations(agent, checkpointer) == []
