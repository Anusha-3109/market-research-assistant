"""Tests for the web page itself.

Streamlit's AppTest runs app.py without a browser: it reports what the page
would show and lets a test click buttons and fill in fields. The agent
behind the page is a fake one (a scripted model, memory held in RAM), so
these tests need no internet and cost nothing.

They check behaviour: what appears and what a click does. How the page
looks (the background, the floating cards) was checked by hand in a browser.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.memory import InMemoryStore
from streamlit.testing.v1 import AppTest

from agent import memory
from agent.agent import assemble_agent, settle_stopped_turn
from agent.config import MissingKeyError
from ui.runtime import Runtime

APP = str(Path(__file__).resolve().parent.parent / "app.py")
SAVED = []


class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


@tool
def save_report(title: str) -> str:
    """Save."""
    SAVED.append(title)
    return f"Report saved as {title}"


def make_runtime(tmp_path, replies: list) -> Runtime:
    """A fake agent with real, temporary memory."""
    import sqlite3

    checkpointer = SqliteSaver(sqlite3.connect(tmp_path / "memory.db", check_same_thread=False),
                               serde=memory.checkpoint_serializer())
    store = InMemoryStore()
    agent = assemble_agent(ScriptedModel(messages=iter(replies)), [], tools=[save_report],
                           checkpointer=checkpointer, store=store)
    return Runtime(agent=agent, checkpointer=checkpointer, store=store)


@pytest.fixture
def page(tmp_path):
    """Returns a function that opens the page with a fake agent giving the
    listed replies. The same fake agent is used for the whole test."""
    SAVED.clear()
    patches = []

    def open_page(replies: list | None = None, runtime: Runtime | None = None):
        runtime = runtime or make_runtime(tmp_path, replies or [])
        patcher = patch("ui.runtime.get_runtime", lambda *args, **kwargs: runtime)
        patcher.start()
        patches.append(patcher)
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.runtime = runtime
        return app

    yield open_page
    for patcher in patches:
        patcher.stop()


def texts(app) -> str:
    """Everything written on the page, as one string."""
    written = list(app.subheader) + list(app.markdown) + list(app.caption)
    return "\n".join(element.value for element in written)


def source_list(app) -> str:
    """The HTML of the source list."""
    return "\n".join(element.proto.body for element in app.get("html")
                     if "gw-sources-head" in element.proto.body)


def button(app, key: str):
    return next(b for b in app.button if b.key == key)


# --- the start screen ---------------------------------------------------------------------

def test_an_empty_conversation_shows_the_headline_and_nine_example_cards(page):
    app = page()

    assert not app.exception
    assert app.title[0].value == "Research **any market**."
    cards = [b for b in app.button if (b.key or "").startswith("card_")]
    assert len(cards) == 9
    assert button(app, "learn").label == "Learn how **Markavi** works."


def test_clicking_an_example_card_asks_its_question_and_shows_the_answer(page):
    app = page([AIMessage("HelloFresh has 11,447 employees.")])

    button(app, "card_5").click().run()

    assert not app.exception
    shown = texts(app)
    assert "How big is HelloFresh?" in shown
    assert "HelloFresh has 11,447 employees." in shown
    # The start screen is gone once the conversation has started.
    assert not [b for b in app.button if (b.key or "").startswith("card_")]


def test_a_typed_question_is_answered(page):
    app = page([AIMessage("About 4% of German households.")])

    app.chat_input[0].set_value("How common are meal kits in Germany?").run()

    assert "About 4% of German households." in texts(app)


def test_the_conversation_is_still_there_when_the_page_is_opened_again(page):
    app = page([AIMessage("First answer.")])
    app.chat_input[0].set_value("First question").run()
    thread_id = app.query_params["c"]

    # A new visit to the same address, as after a refresh.
    again = AppTest.from_file(APP, default_timeout=30)
    again.query_params["c"] = thread_id
    again.run()

    assert "First question" in texts(again)
    assert "First answer." in texts(again)


# --- the research view -----------------------------------------------------------------------

def test_links_in_an_answer_become_numbers_with_a_source_list(page):
    app = page([AIMessage("A box costs 5.93 EUR [source](https://prepmymeal.com/boxen).")])

    app.chat_input[0].set_value("What does Prepmymeal charge?").run()

    shown = texts(app)
    assert "A box costs 5.93 EUR [[1]](https://prepmymeal.com/boxen)." in shown
    # The company named in the question is marked as the official source.
    sources = source_list(app)
    assert "prepmymeal.com" in sources and "Official" in sources


def test_each_question_is_a_tab_and_the_newest_is_shown(page):
    app = page([AIMessage("First answer."), AIMessage("Second answer.")])
    app.chat_input[0].set_value("First question").run()

    app.chat_input[0].set_value("Second question").run()

    assert not app.exception
    tabs = app.button_group[0]
    assert len(tabs.options) == 2
    assert "Second answer." in texts(app)
    assert "First answer." not in texts(app)


def test_an_earlier_tab_shows_its_own_answer(page):
    app = page([AIMessage("First answer."), AIMessage("Second answer.")])
    app.chat_input[0].set_value("First question").run()
    app.chat_input[0].set_value("Second question").run()

    tabs = app.button_group[0]
    tabs.set_value(0).run()

    assert "First answer." in texts(app)
    assert "Second answer." not in texts(app)


def test_research_another_market_opens_an_empty_conversation(page):
    app = page([AIMessage("An answer.")])
    app.chat_input[0].set_value("A question").run()
    first = app.query_params["c"]

    button(app, "another_0").click().run()

    assert app.query_params["c"] != first
    assert app.title[0].value == "Research **any market**."


def test_a_turn_cut_off_mid_tool_is_tidied_so_the_conversation_can_continue(page, tmp_path):
    runtime = make_runtime(tmp_path, [AIMessage("Now a full answer.")])
    config = {"configurable": {"thread_id": "cut"}}
    # What is saved when Stop is pressed while a tool is running: the
    # request for the tool, and no result.
    runtime.agent.update_state(config, {"messages": [
        {"role": "user", "content": "Research it"},
        AIMessage("", tool_calls=[{"name": "save_report", "id": "x1", "args": {"title": "T"}}]),
    ]}, as_node="model")

    assert settle_stopped_turn(runtime.agent, "cut") is True

    messages = runtime.agent.get_state(config).values["messages"]
    assert isinstance(messages[-1], ToolMessage) and messages[-1].tool_call_id == "x1"
    assert settle_stopped_turn(runtime.agent, "cut") is False      # nothing left to tidy


# --- the guide ------------------------------------------------------------------------------

def test_the_wide_card_opens_the_guide_without_calling_the_model(page):
    app = page([])          # no replies: the model must not be needed

    button(app, "learn").click().run()

    assert not app.exception
    assert any("It finds the real competitors." in m.value for m in app.markdown)
    assert button(app, "chip_prices").label == "Where do the prices come from?"


def test_a_follow_up_chip_adds_its_answer_and_then_disappears(page):
    app = page([])
    button(app, "learn").click().run()

    button(app, "chip_prices").click().run()

    assert any("Only from each competitor's own website." in m.value for m in app.markdown)
    assert "chip_prices" not in [b.key for b in app.button]
    assert "chip_competitors" in [b.key for b in app.button]


def test_back_to_start_returns_to_the_cards(page):
    app = page([])
    button(app, "learn").click().run()

    button(app, "chip_back").click().run()

    assert len([b for b in app.button if (b.key or "").startswith("card_")]) == 9


# --- the sidebar ------------------------------------------------------------------------------

def test_a_finished_conversation_is_listed_in_the_sidebar(page):
    app = page([AIMessage("An answer.")])
    app.chat_input[0].set_value("How big is the vegan snack market?").run()

    titles = [b.label for b in app.sidebar.button if (b.key or "").startswith("open_")]

    assert titles == ["How big is the vegan snack market?"]


def test_new_conversation_starts_an_empty_one_with_a_new_address(page):
    app = page([AIMessage("An answer.")])
    app.chat_input[0].set_value("A question").run()
    first = app.query_params["c"]

    button(app.sidebar, "new_conversation").click().run()

    assert app.query_params["c"] != first
    assert app.title[0].value == "Research **any market**."


def test_what_is_remembered_is_shown_and_forget_me_clears_it(page, tmp_path):
    runtime = make_runtime(tmp_path, [])
    memory.save_preference(runtime.store, memory.DEFAULT_USER, "region", "Portugal")
    app = page(runtime=runtime)

    assert any("Portugal" in m.value for m in app.sidebar.markdown)

    button(app.sidebar, "forget_me").click().run()

    assert memory.load_profile(runtime.store, memory.DEFAULT_USER) == {}
    assert not any("Portugal" in m.value for m in app.sidebar.markdown)
    assert "forget_me" not in [b.key for b in app.sidebar.button]


def test_with_nothing_remembered_there_is_no_forget_button(page):
    app = page()

    assert "forget_me" not in [b.key for b in app.sidebar.button]


def test_the_settings_offer_three_models_temperature_and_the_review_switch(page):
    app = page()

    model = app.sidebar.selectbox[0]
    assert model.label == "Model"
    assert len(model.options) == 3
    assert app.sidebar.slider[0].label == "Temperature"
    assert app.sidebar.toggle[0].label == "Review competitors before a report"
    assert app.sidebar.toggle[0].value is True


def test_help_can_open_the_guide(page):
    app = page([])

    button(app.sidebar, "help_guide").click().run()

    assert any("It finds the real competitors." in m.value for m in app.markdown)


# --- approval ------------------------------------------------------------------------------------

SAVE_CALL = AIMessage("", tool_calls=[{"name": "save_report", "id": "s1",
                                       "args": {"title": "Meal kits Germany"}}])


def test_a_save_request_shows_the_approval_form_and_locks_the_question_box(page):
    app = page([SAVE_CALL, AIMessage("Saved.")])

    app.chat_input[0].set_value("Save this report.").run()

    assert not app.exception
    assert SAVED == []                                     # nothing written yet
    assert app.text_input[0].label == "Title"
    assert app.text_input[0].value == "Meal kits Germany"
    assert app.chat_input[0].disabled
    assert app.chat_input[0].placeholder == "Answer the question above to continue"


def test_pressing_save_writes_under_the_title_in_the_form(page):
    app = page([SAVE_CALL, AIMessage("Saved.")])
    app.chat_input[0].set_value("Save this report.").run()

    app.text_input[0].set_value("My own title")
    button(app, "FormSubmitter:save_form-Save").click().run()

    assert not app.exception
    assert SAVED == ["My own title"]
    assert not app.chat_input[0].disabled


def test_pressing_dont_save_writes_nothing(page):
    app = page([SAVE_CALL, AIMessage("All right, not saved.")])
    app.chat_input[0].set_value("Save this report.").run()

    button(app, "FormSubmitter:save_form-Don't save").click().run()

    assert SAVED == []
    assert "All right, not saved." in texts(app)


def test_settings_are_locked_while_an_approval_is_waiting(page):
    app = page([SAVE_CALL, AIMessage("Saved.")])
    app.chat_input[0].set_value("Save this report.").run()

    assert app.sidebar.selectbox[0].disabled
    assert app.sidebar.toggle[0].disabled


# --- setup problems ---------------------------------------------------------------------------------

def test_a_missing_api_key_shows_setup_steps_instead_of_crashing():
    def no_key(*args, **kwargs):
        raise MissingKeyError("OPENROUTER_API_KEY is not set.")

    with patch("ui.runtime.get_runtime", no_key):
        app = AppTest.from_file(APP, default_timeout=30).run()

    assert not app.exception
    assert app.error[0].value == "OPENROUTER_API_KEY is not set."
    assert any(".env.example" in m.value for m in app.markdown)


# --- the source list ----------------------------------------------------------------------------

def test_a_source_row_shows_number_icon_title_site_and_badge():
    from agent.citations import Source
    from ui.research import source_row

    row = source_row(Source(2, "Earnings Presentation", "stock.walmart.com",
                            "https://stock.walmart.com/q1", True))

    assert '<span class="gw-source-number">2</span>' in row
    assert "url(https://stock.walmart.com/favicon.ico)" in row
    assert "Earnings Presentation" in row and "<code>stock.walmart.com</code>" in row
    assert "Official" in row


def test_text_from_the_web_cannot_act_as_markup_in_the_source_list():
    from agent.citations import Source
    from ui.research import source_row

    row = source_row(Source(1, '<script>x</script> "T"', "a.example", "https://a.example/?q=\"><b>"))

    assert "<script>" not in row and "<b>" not in row


# --- tab labels ------------------------------------------------------------------------------------

def test_tabs_with_the_same_wording_get_different_labels():
    from agent.session import Block, Turn
    from ui.research import tab_labels

    turns = [Turn("Give me a report", Block("assistant", text="One")),
             Turn("Give me a report", Block("assistant", text="Two")),
             Turn("Give me a report", None)]

    assert tab_labels(turns, 40) == ["Give me a report", "Give me a report (2)",
                                     "Give me a report (3)"]


def test_a_report_tab_is_named_after_the_report():
    from agent.session import Block, Turn
    from ui.research import tab_labels

    report = "# Market research report: oat milk in Germany"
    turns = [Turn("Give me a market research report for oat milk in Germany",
                  Block("assistant", report=report))]

    assert tab_labels(turns, 40) == ["oat milk in Germany"]


def test_asking_the_same_question_twice_still_opens_the_right_answer(page):
    app = page([AIMessage("First answer."), AIMessage("Second answer.")])
    app.chat_input[0].set_value("Same question").run()
    app.chat_input[0].set_value("Same question").run()

    tabs = app.button_group[0]
    tabs.set_value(0).run()

    assert "First answer." in texts(app)
    assert "Second answer." not in texts(app)
