"""Tests for what makes the app personal once someone has signed in: their
settings are kept, they are greeted by name, and they can sign out.

The page is run without a browser. Anna and Ben are made-up people.
"""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.store.memory import InMemoryStore

from agent import memory, styles
from tests.test_app import button
from tests.test_sign_in import PASSWORD, START_TITLE, create, sign_in, site  # noqa: F401
from tests.test_styles import ListeningModel
from tests.test_two_accounts import ANNA, BEN, ask, listed, two_accounts, visit_as

DEFAULTS = {"model": "openai/gpt-4.1-mini", "temperature": 0.2, "length": "No limit",
            "style": "Balanced", "review": True, "language": "en", "theme": "light"}


def choose(app, **choices):
    """Change settings on the Admin page, one after the other, as a person
    would."""
    next(b for b in app.button if b.key == "page_admin").click().run()
    for name, value in choices.items():
        widget = next(w for w in list(app.selectbox) + list(app.select_slider)
                      + list(app.slider) + list(app.toggle)
                      if w.key == f"set_{name}")
        widget.set_value(value).run()
    return app


def shown(app, name: str):
    """What a setting in the sidebar shows."""
    return app.session_state[f"set_{name}"]


def html_on(part) -> str:
    return "\n".join(element.proto.body for element in part.get("html"))


# --- keeping settings ------------------------------------------------------------------------

def test_the_defaults_are_what_the_app_ships_with():
    from agent import config

    assert DEFAULTS == {"model": config.MODEL_NAME, "temperature": config.TEMPERATURE,
                        "length": config.ANSWER_LENGTH, "style": config.ANSWER_STYLE,
                        "review": config.REVIEW_COMPETITORS, "language": config.LANGUAGE,
                        "theme": config.THEME}


def test_a_new_account_has_the_default_settings():
    assert memory.load_settings(InMemoryStore(), ANNA) == DEFAULTS


def test_saved_settings_come_back_for_that_account_only():
    store = InMemoryStore()
    chosen = {"model": "openai/gpt-4.1-mini", "temperature": 0.7, "length": "Short",
              "style": "Friendly", "review": False, "language": "de", "theme": "dark"}

    memory.save_settings(store, ANNA, chosen)

    assert memory.load_settings(store, ANNA) == chosen
    assert memory.load_settings(store, BEN) == DEFAULTS


@pytest.mark.parametrize("name, bad", [
    ("model", "a-model/that-is-not-offered"), ("temperature", 7), ("temperature", "hot"),
    ("length", "Endless"), ("style", "Rude"), ("review", "yes"),
])
def test_a_stored_value_that_is_not_a_valid_choice_falls_back_to_the_default(name, bad):
    store = InMemoryStore()
    store.put(("users", ANNA), "settings", {**DEFAULTS, "style": "Formal", name: bad})

    loaded = memory.load_settings(store, ANNA)

    assert loaded[name] == DEFAULTS[name]
    if name != "style":
        assert loaded["style"] == "Formal"          # the valid ones are kept


# --- settings on the page ----------------------------------------------------------------------

def test_settings_chosen_on_the_admin_page_are_there_at_the_next_sign_in(site):  # noqa: F811
    two_accounts(site)
    with patch("agent.config.ADMIN_USERNAMES", {"anna"}):
        choose(visit_as(site, "anna"), style="Friendly", length="Short", temperature=0.7,
               review=False)

    again = visit_as(site, "anna")

    assert not again.exception
    assert [shown(again, name) for name in ("style", "length", "temperature", "review")] == \
        ["Friendly", "Short", 0.7, False]


def test_settings_the_admin_chooses_reach_every_account(site):  # noqa: F811
    two_accounts(site)
    with patch("agent.config.ADMIN_USERNAMES", {"anna"}):
        choose(visit_as(site, "anna"), style="Friendly", length="Short")

    ben = visit_as(site, "ben")

    assert [shown(ben, name) for name in ("style", "length")] == ["Friendly", "Short"]


def test_the_agent_follows_the_settings_that_came_back(site):  # noqa: F811
    model = ListeningModel(messages=iter([AIMessage("ok")]))
    two_accounts(site, model=model)
    with patch("agent.config.ADMIN_USERNAMES", {"anna"}):
        choose(visit_as(site, "anna"), style="Friendly")

    ask(visit_as(site, "anna"), "How big is the oat milk market?")

    assert styles.STYLE_INSTRUCTIONS["Friendly"] in model.told()


def test_changing_a_setting_writes_the_copy_for_the_cloud(site):  # noqa: F811
    from unittest.mock import patch

    two_accounts(site)
    with patch("agent.config.ADMIN_USERNAMES", {"anna"}):
        app = visit_as(site, "anna")
        with patch("agent.memory.backup_memory") as copy_made:
            choose(app, style="Friendly")

    copy_made.assert_called()


# --- the greeting ----------------------------------------------------------------------------------

def test_a_new_account_is_welcomed_by_name(site):  # noqa: F811
    site.allow_agent()

    app = create(site.visit(), name="Anna Berg", username="anna")

    assert "Welcome, Anna Berg" in html_on(app.main)


def test_an_account_that_returns_is_welcomed_back(site):  # noqa: F811
    two_accounts(site)

    assert "Welcome back, Anna" in html_on(visit_as(site, "anna").main)


def test_a_name_is_shown_as_text_never_as_markup(site):  # noqa: F811
    site.allow_agent()

    app = create(site.visit(), name="<b>Anna</b>", username="anna")

    assert "Welcome, &lt;b&gt;Anna&lt;/b&gt;" in html_on(app.main)
    assert "<b>Anna</b>" not in html_on(app.main) + html_on(app.sidebar)


def test_without_accounts_nobody_is_greeted_and_there_is_no_badge(page):
    app = page()

    assert "Welcome" not in html_on(app.main)
    assert "sign_out" not in [b.key for b in app.button]
    assert "Signed in as" not in html_on(app.main) + html_on(app.sidebar)


# --- the badge at the top right, and signing out ------------------------------------------------

def in_order(block) -> list[str]:
    """What a part of the page shows, from top to bottom: the text of each
    element, or the label of a button or a folding section."""
    seen = []
    for child in block.children.values():
        if hasattr(child, "children"):
            seen.append(getattr(child, "label", "") or "")
            seen += in_order(child)
        elif child.type == "html":
            seen.append(child.proto.body)
        else:
            seen.append(str(getattr(child, "label", "") or getattr(child, "value", "")))
    return seen


def position(sequence: list[str], words: str) -> int:
    return next(index for index, text in enumerate(sequence) if words in text)


def badge(app):
    """The round badge at the bottom of the sidebar: a folding menu whose
    label is one letter."""
    return next(block for block in app.sidebar.get("popover"))


def letter_on(popover) -> str:
    return popover.proto.popover.label


def test_the_badge_shows_the_first_letter_of_your_name(site):  # noqa: F811
    two_accounts(site)

    assert letter_on(badge(visit_as(site, "anna"))) == "A"
    assert letter_on(badge(visit_as(site, "ben"))) == "B"


def test_the_badge_opens_to_who_is_signed_in_and_sign_out(site):  # noqa: F811
    two_accounts(site)

    inside = in_order(badge(visit_as(site, "anna")))

    assert position(inside, "Signed in as <span class=\"gw-account-name\">Anna</span>") \
        < position(inside, "Sign out")
    assert not any("Ben" in text for text in inside)


def test_the_badge_is_at_the_bottom_of_the_sidebar_under_help(site):  # noqa: F811
    two_accounts(site)
    memory.save_preference(site.store, ANNA, "region", "Portugal")

    app = visit_as(site, "anna")
    sidebar = in_order(app.sidebar)

    assert (position(sidebar, "New conversation") < position(sidebar, "What I remember")
            < position(sidebar, "Forget me") < position(sidebar, "Help")
            < position(sidebar, "Signed in as") < position(sidebar, "Sign out"))
    assert list(app.main.get("popover")) == []           # no badge at the top right any more


def test_the_badge_is_in_the_sidebar_of_the_other_pages_too(site):  # noqa: F811
    two_accounts(site)
    app = visit_as(site, "anna")

    button(app, "page_dashboard").click().run()

    assert letter_on(badge(app)) == "A"
    button(app, "sign_out").click().run()
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]


def test_signing_out_brings_back_the_sign_in_screen(site):  # noqa: F811
    two_accounts(site)
    app = visit_as(site, "anna")

    button(app, "sign_out").click().run()

    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]
    assert "account" not in app.session_state
    assert len(app.chat_input) == 0


def test_the_next_person_on_the_same_browser_gets_nothing_from_the_one_before(site):  # noqa: F811
    two_accounts(site, replies=[AIMessage("An answer for Anna.")])
    app = visit_as(site, "anna")
    switch_language = next(c for c in app.segmented_control if (c.key or "").startswith("language_switch"))
    switch_language.set_value("de").run()
    ask(app, "Anna's question about oat milk")
    button(app, "sign_out").click().run()

    sign_in(app, "ben", PASSWORD)

    assert app.title[0].value == START_TITLE          # not Anna's conversation
    assert listed(app) == []
    assert shown(app, "language") == "en"              # Anna's own choice stays hers
    assert "Welcome back, Ben" in html_on(app.main)


from tests.test_app import page  # noqa: E402,F401  (a fixture)
