"""Tests for the Light | Dark switch at the top right, beside EN | DE.

Dark is drawn by one style rule that turns the page's colours around and
then back again for pictures, so the logo and the robot keep their colours.
The choice is kept with the account, like the language.
"""

from langgraph.store.memory import InMemoryStore

from agent import memory
from agent.app_settings import SHARED
from tests.test_app import page  # noqa: F401  (page is a fixture)
from tests.test_language import switch as language_switch
from tests.test_sign_in import site  # noqa: F401  (site is a fixture)
from tests.test_two_accounts import ANNA, two_accounts, visit_as


def theme_switch(app):
    return next(control for control in app.segmented_control if (control.key or "").startswith("theme_switch"))


def dark_style(app) -> bool:
    return any("gw-dark" in element.proto.body for element in app.get("html"))


def test_the_switch_offers_light_and_dark_and_starts_on_light(page):  # noqa: F811
    app = page()

    assert theme_switch(app).options == ["Light", "Dark"]       # each with its icon
    assert theme_switch(app).value == "light"
    assert not dark_style(app)


def test_choosing_dark_darkens_the_page_and_stays_on_the_next_click(page):  # noqa: F811
    app = page()

    theme_switch(app).set_value("dark").run()
    app.run()

    assert theme_switch(app).value == "dark"
    assert dark_style(app)


def test_clicking_the_chosen_theme_again_does_not_switch_it_off(page):  # noqa: F811
    app = page()
    theme_switch(app).set_value("dark").run()

    theme_switch(app).set_value(None).run()

    assert theme_switch(app).value == "dark"


def test_the_switch_follows_the_language(page):  # noqa: F811
    app = page()

    language_switch(app).set_value("de").run()

    assert theme_switch(app).options == ["Hell", "Dunkel"]


def test_the_theme_is_a_choice_of_each_account_not_of_the_app():
    store = InMemoryStore()
    memory.save_settings(store, ANNA, {"theme": "dark"})

    assert memory.load_settings(store, ANNA)["theme"] == "dark"
    assert memory.load_settings(InMemoryStore(), ANNA)["theme"] == "light"
    assert "theme" not in SHARED


def test_a_stored_theme_the_app_does_not_have_falls_back_to_light():
    store = InMemoryStore()
    store.put(("users", ANNA), "settings", {"theme": "purple"})

    assert memory.load_settings(store, ANNA)["theme"] == "light"


def test_the_theme_an_account_chose_is_there_at_its_next_sign_in(site):  # noqa: F811
    two_accounts(site)
    theme_switch(visit_as(site, "anna")).set_value("dark").run()

    again = visit_as(site, "anna")

    assert theme_switch(again).value == "dark" and dark_style(again)
    assert theme_switch(visit_as(site, "ben")).value == "light"
