"""Tests for the Admin page: developer settings for the whole app.

The model, temperature, answer length, answer style, competitor review,
the system prompt and which tools the agent may use are set here, once,
for every account. Only an admin can open the page.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langgraph.store.memory import InMemoryStore

from agent.agent import enabled_tools
from agent.app_settings import load_app_settings, save_app_settings
from agent.usage import Usage
from agent.usage_log import ANSWERED, record
from tests.test_app import button, make_runtime, page  # noqa: F401  (page is a fixture)
from tests.test_sign_in import site  # noqa: F401  (site is a fixture)
from tests.test_styles import ListeningModel
from tests.test_two_accounts import ask, two_accounts, visit_as


def open_admin(app):
    button(app, "page_admin").click().run()
    assert not app.exception
    return app


def back(app):
    button(app, "page_research").click().run()
    return app


def widget(app, key):
    for kind in (app.selectbox, app.select_slider, app.slider, app.toggle, app.text_area):
        found = [w for w in kind if w.key == key]
        if found:
            return found[0]
    raise AssertionError(f"no widget {key}")


def listening_app(page, tmp_path):  # noqa: F811
    model = ListeningModel(messages=iter([AIMessage("ok") for _ in range(10)]))
    runtime = make_runtime(tmp_path, [], model=model)
    return page(runtime=runtime), model, runtime


# --- the stored settings ---------------------------------------------------------------------------

def test_the_app_settings_start_at_the_defaults():
    settings = load_app_settings(InMemoryStore())

    assert settings["model"] == "openai/gpt-4.1-mini" and settings["style"] == "Balanced"
    assert settings["prompt"] == "" and settings["disabled_tools"] == []


def test_a_value_that_is_not_a_choice_falls_back_to_the_default():
    store = InMemoryStore()
    save_app_settings(store, {"style": "Rude", "disabled_tools": ["web_search", "no_such_tool"]})

    settings = load_app_settings(store)

    assert settings["style"] == "Balanced"
    assert settings["disabled_tools"] == ["web_search"]


def test_a_switched_off_tool_is_not_given_to_the_agent():
    names = [tool.name for tool in enabled_tools(["web_search", "get_company_financials"])]

    assert "web_search" not in names and "get_company_financials" not in names
    assert "create_market_report" in names and "search_news" in names


# --- the page ------------------------------------------------------------------------------------

def test_the_admin_page_has_its_cards_settings_prompt_and_tools(page, tmp_path):  # noqa: F811
    store = InMemoryStore()
    record(store, "local", ANSWERED, seconds=5.0, when=datetime.now(timezone.utc),
           usage=Usage(calls=1, input_tokens=900, output_tokens=100, cost=0.007, priced_calls=1))
    app = open_admin(page(runtime=make_runtime(tmp_path, [], store=store)))

    assert "Admin" in [t.value for t in app.title]
    assert [tab.label for tab in app.tabs] == ["Developer settings", "Feedback", "Documentation"]
    shown = "\n".join(e.proto.body for e in app.get("html") if "gw-kpi" in e.proto.body)
    for label in ("Cost today", "Answers today", "Helpful", "Active accounts"):
        assert label in shown, label
    assert "$0.007" in shown and "No ratings yet" in shown
    assert widget(app, "set_model").label == "Model"
    assert widget(app, "admin_prompt").value.startswith("You are a market research assistant")
    assert len([t for t in app.toggle if (t.key or "").startswith("tool_")]) == 9


def test_the_settings_are_no_longer_in_the_sidebar(page):  # noqa: F811
    app = page()

    assert [e.label for e in app.sidebar.expander] == ["Help"]


def test_a_style_set_on_the_admin_page_reaches_the_model(page, tmp_path):  # noqa: F811
    app, model, runtime = listening_app(page, tmp_path)
    open_admin(app)

    widget(app, "set_style").set_value("Concise").run()
    back(app).chat_input[0].set_value("How big is the oat milk market?").run()

    assert 'The user chose the "Concise" answer style' in model.told()
    assert load_app_settings(runtime.store)["style"] == "Concise"


def test_a_saved_prompt_replaces_the_built_in_one_and_restore_brings_it_back(page, tmp_path):  # noqa: F811
    app, model, runtime = listening_app(page, tmp_path)
    open_admin(app)

    widget(app, "admin_prompt").set_value("You are a test assistant. Today is {today}.")
    button(app, "admin_prompt_save").click().run()
    back(app).chat_input[0].set_value("Hello?").run()
    assert model.told().startswith("You are a test assistant. Today is 20")

    open_admin(app)
    button(app, "admin_prompt_restore").click().run()
    assert load_app_settings(runtime.store)["prompt"] == ""


def test_switching_a_tool_off_saves_it_and_reaches_the_agent(page, tmp_path):  # noqa: F811
    runtime = make_runtime(tmp_path, [])
    asked = []

    def get_runtime(*args, **kwargs):
        asked.append(kwargs.get("disabled_tools", args[2] if len(args) > 2 else ()))
        return runtime

    page(runtime=runtime)
    with patch("ui.runtime.get_runtime", get_runtime):
        from streamlit.testing.v1 import AppTest

        from tests.test_app import APP
        app = AppTest.from_file(APP, default_timeout=30).run()
        open_admin(app)
        widget(app, "tool_web_search").set_value(False).run()

    assert load_app_settings(runtime.store)["disabled_tools"] == ["web_search"]
    assert tuple(asked[-1]) == ("web_search",)


# --- who may open it -----------------------------------------------------------------------------

def test_an_account_that_is_not_an_admin_cannot_open_the_page(site):  # noqa: F811
    two_accounts(site)
    with patch("agent.config.ADMIN_USERNAMES", {"anna"}):
        ben = visit_as(site, "ben")
        ben.session_state["page"] = "admin"
        ben.run()

    assert "admin" not in [b.key.removeprefix("page_") for b in ben.sidebar.button
                           if (b.key or "").startswith("page_")]
    assert "Admin" not in [t.value for t in ben.title]


def test_settings_an_admin_chooses_apply_to_every_account(site):  # noqa: F811
    model = ListeningModel(messages=iter([AIMessage("ok") for _ in range(5)]))
    two_accounts(site, model=model)
    with patch("agent.config.ADMIN_USERNAMES", {"anna"}):
        anna = open_admin(visit_as(site, "anna"))
        widget(anna, "set_style").set_value("Friendly").run()

        ask(visit_as(site, "ben"), "How big is the oat milk market?")

    assert 'The user chose the "Friendly" answer style' in model.told()
