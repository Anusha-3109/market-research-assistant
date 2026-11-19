"""Tests for the "Maximum answer length" setting.

The limit is a hard cap on how much the model may write in one chat answer.
Each test runs a real chat turn through the agent with a fake model, and
looks at two things: the settings the model was called with, and the answer
that was saved.
"""

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agent.agent import assemble_agent, stream_steps
from agent.memory import UserContext
from agent.session import load_messages
from tests.test_styles import ListeningModel, write_report


def chat(limit: int | None, replies: list | None = None, tools: list | None = None):
    """Ask one question with this answer length limit. Returns the fake
    model (to see how it was called) and the saved messages."""
    model = ListeningModel(messages=iter(replies or [AIMessage("A full answer.")]))
    agent = assemble_agent(model, [], tools=tools or [], checkpointer=InMemorySaver(),
                           store=InMemoryStore(), extract_facts=lambda message: {})
    context = UserContext(user_id="tester", max_answer_tokens=limit)
    list(stream_steps(agent, "How big is HelloFresh?", "thread-1", context=context))
    return model, load_messages(agent, "thread-1")


# --- the limit reaches the model ---------------------------------------------------------------

def test_the_chosen_limit_is_set_on_the_model_call():
    model, _ = chat(limit=250)

    assert model.settings[-1]["max_tokens"] == 250


def test_without_a_limit_the_model_is_called_as_before():
    model, _ = chat(limit=None)

    assert "max_tokens" not in model.settings[-1]


def test_a_setting_that_is_not_a_sensible_number_means_no_limit():
    for nonsense in (0, -5, "250", True):
        model, _ = chat(limit=nonsense)

        assert "max_tokens" not in model.settings[-1], nonsense


# --- an answer that the limit cut off ----------------------------------------------------------
# The model service says why it stopped writing: "length" means the limit
# was reached, "stop" means the model had finished.

NOTE = "*This answer was cut off by the maximum answer length chosen in Settings.*"


def stopped(text: str, why: str) -> AIMessage:
    return AIMessage(text, response_metadata={"finish_reason": why})


def test_an_answer_cut_off_by_the_limit_says_so():
    _, saved = chat(limit=250, replies=[stopped("HelloFresh is a large company with a", "length")])

    assert saved[-1].content == f"HelloFresh is a large company with a\n\n{NOTE}"


def test_an_answer_that_finished_within_the_limit_is_not_touched():
    _, saved = chat(limit=250, replies=[stopped("HelloFresh employs 11,447 people.", "stop")])

    assert saved[-1].content == "HelloFresh employs 11,447 people."


def test_without_a_limit_nothing_is_said_about_settings():
    # The model can also stop at its own built-in maximum. That is not the
    # user's setting, so the note would be untrue.
    _, saved = chat(limit=None, replies=[stopped("A very long answer that", "length")])

    assert saved[-1].content == "A very long answer that"


# --- a step that the limit cut off -------------------------------------------------------------
# Before it answers, the model may ask for a tool. If the limit cuts that
# request short it is useless, and the research would stop. Such a step is
# asked for again without the limit.

def figures_tool():
    from langchain_core.tools import StructuredTool
    return StructuredTool.from_function(
        lambda company: "Employees: 11447", name="get_company_financials",
        description="Look up company figures.")


def asks_for_figures(why: str) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "get_company_financials", "id": "call-1",
                                      "args": {"company": "HelloFresh"}}],
                     response_metadata={"finish_reason": why})


def test_a_request_for_a_tool_that_was_cut_off_is_asked_for_again_without_the_limit():
    model, saved = chat(limit=250, tools=[figures_tool()],
                        replies=[asks_for_figures("length"),      # cut off
                                 asks_for_figures("tool_calls"),  # asked again, complete
                                 stopped("HelloFresh employs 11,447 people.", "stop")])

    assert [call.get("max_tokens") for call in model.settings] == [250, None, 250]
    assert [type(message).__name__ for message in saved] == \
        ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    assert saved[1].content == ""                     # no note on a step
    assert saved[-1].content == "HelloFresh employs 11,447 people."


def test_a_cut_off_reply_with_nothing_in_it_is_asked_for_again_too():
    model, saved = chat(limit=250, replies=[stopped("", "length"),
                                            stopped("HelloFresh employs 11,447 people.", "stop")])

    assert [call.get("max_tokens") for call in model.settings] == [250, None]
    assert saved[-1].content == "HelloFresh employs 11,447 people."


# --- together with the other checks ------------------------------------------------------------

def test_an_answer_that_was_cut_off_still_gets_its_source():
    from tests.test_source_check import FIGURES, FIGURES_LINK, fake_tools, uses

    model, saved = chat(limit=250, tools=fake_tools([FIGURES]),
                        replies=[uses(FIGURES[0], 1), stopped("HelloFresh is a large", "length")])

    assert saved[-1].content == (f"HelloFresh is a large\n\n{NOTE}\n\n"
                                 f"Sources: [source]({FIGURES_LINK})")


# --- reports -----------------------------------------------------------------------------------
# A report is built from several structured answers of the model. A cut-off
# one would break it, so the limit is for chat answers only.

def test_a_report_comes_back_whole_whatever_the_limit_is():
    context = UserContext(user_id="tester", max_answer_tokens=250, review_competitors=False)

    _, saved, _ = write_report(context)

    report = saved[-1].content
    assert type(saved[-1]).__name__ == "ToolMessage"        # the report itself, shown as it is
    for heading in ("## 1. Market overview", "## 2. Competitors", "## 3. Pricing",
                    "## 4. Trends", "## 5. SWOT analysis", "## 6. References"):
        assert heading in report, heading
    assert NOTE not in report


def test_the_limit_applies_to_the_chat_model_that_asks_for_the_report():
    # The cap is on the chat model's own messages. Asking for the report is
    # one of them; writing the report is not.
    context = UserContext(user_id="tester", max_answer_tokens=250, review_competitors=False)

    _, _, chat_model = write_report(context)

    assert [call.get("max_tokens") for call in chat_model.settings] == [250]


# --- the setting on the page -------------------------------------------------------------------

from tests.test_app import make_runtime, page  # noqa: E402,F401  (page is a fixture)


def open_app(page, tmp_path, replies: list | None = None):
    model = ListeningModel(messages=iter(replies or [AIMessage("ok") for _ in range(20)]))
    return page(runtime=make_runtime(tmp_path, [], model=model)), model


def length_setting(app):
    """The setting on the Admin page; the page is opened first."""
    if not [s for s in app.select_slider if s.key == "set_length"]:
        next(b for b in app.button if b.key == "page_admin").click().run()
    return next(s for s in app.select_slider if s.label == "Maximum answer length")


def back(app):
    next(b for b in app.button if b.key == "page_research").click().run()
    return app


def test_the_settings_offer_four_lengths_with_no_limit_chosen(page, tmp_path):
    app, _ = open_app(page, tmp_path)

    setting = length_setting(app)

    assert list(setting.options) == ["Short", "Medium", "Long", "No limit"]
    assert setting.value == "No limit"


def test_a_length_picked_in_the_settings_limits_the_next_answer(page, tmp_path):
    app, model = open_app(page, tmp_path)

    length_setting(app).set_value("Short").run()
    back(app).chat_input[0].set_value("How big is the oat milk market?").run()

    assert not app.exception
    assert model.settings[-1]["max_tokens"] == 250


def test_each_position_of_the_slider_has_its_own_limit(page, tmp_path):
    app, model = open_app(page, tmp_path)

    limits = {}
    for position in ("Medium", "Long", "No limit"):
        length_setting(app).set_value(position).run()
        back(app).chat_input[0].set_value(f"A question at {position}").run()
        limits[position] = model.settings[-1].get("max_tokens")

    assert limits == {"Medium": 600, "Long": 1200, "No limit": None}
