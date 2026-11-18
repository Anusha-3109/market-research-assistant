"""Tests for the sidebar of an open conversation: the conversation picker
and the links that switch between the views of a conversation.

The page is run without a browser, with a fake agent.
"""

from langchain_core.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

from tests.test_app import APP, button, make_runtime, page, texts  # noqa: F401  (page is a fixture)

REPORT = ("# Market research report: oat milk in Germany\n\n## 1. Market overview\n\n"
          "- Oat milk market value: 1 billion EUR (Germany, 2025).")


def ask(app, question: str):
    app.chat_input[0].set_value(question).run()
    return app


def address(app) -> str:
    value = app.query_params["c"]
    return value[0] if isinstance(value, list) else value


def picker(app):
    """The conversation picker in the sidebar, or None."""
    return next((box for box in app.sidebar.selectbox if box.label == "Conversation"), None)


def listed(app) -> list[str]:
    """The conversations listed as buttons in the sidebar."""
    return [b.label for b in app.sidebar.button if (b.key or "").startswith("open_")]


def view_links(app) -> list[str]:
    return [b.label for b in app.sidebar.button if (b.key or "").startswith("view_")]


def with_a_report(page, tmp_path):  # noqa: F811
    """The page opened at a conversation that holds one report."""
    runtime = make_runtime(tmp_path, [AIMessage("A follow-up answer.")])
    wants_report = AIMessage("", tool_calls=[{"name": "create_market_report", "id": "r1",
                                              "args": {"product": "oat milk", "country": "Germany"}}])
    report = ToolMessage(REPORT, tool_call_id="r1", name="create_market_report",
                         artifact={"problems": [], "log": []})
    runtime.agent.update_state({"configurable": {"thread_id": "rep"}}, {"messages": [
        {"role": "user", "content": "A report on oat milk in Germany"}, wants_report, report]},
        as_node="tools")
    page(runtime=runtime)                                  # puts the fake agent in place
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["c"] = "rep"
    return app.run()


# --- the front page keeps its sidebar ----------------------------------------------------------

def test_the_front_page_lists_conversations_and_has_no_picker_or_view_links(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "How big is the oat milk market?")

    button(app, "bar_new").click().run()                   # back to the front page

    assert listed(app) == ["How big is the oat milk market?"]
    assert picker(app) is None
    assert view_links(app) == []


# --- the conversation picker --------------------------------------------------------------------

def test_an_open_conversation_shows_a_picker_with_itself_chosen(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "How big is the oat milk market?")

    assert not app.exception
    assert listed(app) == []                               # the list gives way to the picker
    assert picker(app).value == address(app)
    assert picker(app).options[picker(app).index] == "How big is the oat milk market?"


def test_picking_another_conversation_opens_it(page):  # noqa: F811
    app = ask(page([AIMessage("First answer."), AIMessage("Second answer.")]), "First question")
    first = address(app)
    button(app, "bar_new").click().run()
    ask(app, "Second question")
    assert "Second answer." in texts(app)

    picker(app).set_value(first).run()

    assert not app.exception
    assert address(app) == first
    assert "First answer." in texts(app) and "Second answer." not in texts(app)
    assert picker(app).value == first


def test_a_new_conversation_does_not_jump_back_to_the_one_picked_before(page):  # noqa: F811
    app = ask(page([AIMessage("First answer."), AIMessage("Second answer."),
                    AIMessage("Third answer.")]), "First question")
    first = address(app)
    button(app, "bar_new").click().run()
    ask(app, "Second question")
    picker(app).set_value(first).run()

    button(app, "bar_new").click().run()
    ask(app, "Third question")

    assert address(app) != first
    assert "Third answer." in texts(app)


# --- the view links ---------------------------------------------------------------------------------

def test_a_conversation_without_a_report_offers_only_ask(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "How big is the oat milk market?")

    assert view_links(app) == ["Ask"]


def test_a_conversation_with_a_report_offers_ask_and_report(page, tmp_path):  # noqa: F811
    app = with_a_report(page, tmp_path)

    assert not app.exception
    assert view_links(app) == ["Ask", "Report"]


def test_a_conversation_opens_on_ask_with_the_chat(page, tmp_path):  # noqa: F811
    app = with_a_report(page, tmp_path)

    assert button(app, "view_ask").proto.type == "secondary"       # the active link is filled
    assert button(app, "view_report").proto.type == "tertiary"
    assert "suggest_0" in [b.key for b in app.button]


def test_report_shows_the_report_alone_without_the_chat(page, tmp_path):  # noqa: F811
    app = with_a_report(page, tmp_path)

    button(app, "view_report").click().run()

    assert not app.exception
    assert button(app, "view_report").proto.type == "secondary"
    assert "Oat milk market value: 1 billion EUR (Germany, 2025)." in texts(app)
    assert "suggest_0" not in [b.key for b in app.button]
    assert len(app.chat_input) == 0


def test_ask_brings_the_chat_back(page, tmp_path):  # noqa: F811
    app = with_a_report(page, tmp_path)
    button(app, "view_report").click().run()

    button(app, "view_ask").click().run()

    assert "suggest_0" in [b.key for b in app.button]
    assert len(app.chat_input) == 1


def test_another_conversation_opens_on_ask_again(page, tmp_path):  # noqa: F811
    app = with_a_report(page, tmp_path)
    button(app, "view_report").click().run()

    button(app.sidebar, "new_conversation").click().run()
    ask(app, "A question in a new conversation")

    assert view_links(app) == ["Ask"]
    assert "suggest_0" in [b.key for b in app.button]


# --- two conversations with the same title ---------------------------------------------------------
#
# The browser tells the picker which entry is chosen by its text. Two entries
# reading the same were mixed up: any click in one conversation jumped to the
# other. So every entry must read differently.

def test_conversations_with_the_same_title_get_different_entries():
    from agent.session import Conversation
    from ui.sidebar import picker_entries

    same = "Give me a market research report for gluten…"
    entries = picker_entries([Conversation("a1", same), Conversation("b2", "Oat milk"),
                              Conversation("c3", same), Conversation("d4", same)],
                             current="c3", title=same)

    assert entries == {"c3": same, "a1": same + " (2)", "b2": "Oat milk", "d4": same + " (3)"}
    assert len(set(entries.values())) == len(entries)


def test_the_open_conversation_is_listed_first_even_if_it_is_not_among_the_recent_ones():
    from agent.session import Conversation
    from ui.sidebar import picker_entries

    entries = picker_entries([Conversation("a1", "Oat milk")], current="old", title="An older one")

    assert list(entries) == ["old", "a1"]
    assert entries["old"] == "An older one"


def test_the_picker_on_the_page_has_no_two_entries_reading_the_same(page):  # noqa: F811
    app = page([AIMessage("First answer."), AIMessage("Second answer.")])
    ask(app, "The very same question")
    button(app.sidebar, "new_conversation").click().run()
    ask(app, "The very same question")

    options = picker(app).options

    assert len(options) == 2 and len(set(options)) == 2
