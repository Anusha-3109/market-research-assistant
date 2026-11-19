"""Tests for the Light | Dark choice on the Admin page.

Like the other settings there, it applies to the whole app: when the admin
picks Dark, every account sees dark. Dark is drawn by one style rule that
turns the page's colours around and back again for pictures, so the logo
and the robot keep their colours.
"""

from unittest.mock import patch

from langgraph.store.memory import InMemoryStore

from agent.app_settings import SHARED, load_app_settings
from tests.test_app import button, make_runtime, page  # noqa: F401  (page is a fixture)
from tests.test_language import switch as language_switch
from tests.test_sign_in import site  # noqa: F401  (site is a fixture)
from tests.test_two_accounts import two_accounts, visit_as


def open_admin(app):
    button(app, "page_admin").click().run()
    assert not app.exception
    return app


def theme_setting(app):
    return next(control for control in app.segmented_control if control.key == "set_theme")


def dark_style(app) -> bool:
    return any("gw-dark" in element.proto.body for element in app.get("html"))


def test_the_theme_is_a_setting_of_the_whole_app():
    assert "theme" in SHARED
    assert load_app_settings(InMemoryStore())["theme"] == "light"


def test_the_switch_is_on_the_admin_page_and_no_longer_at_the_top_right(page):  # noqa: F811
    app = page()
    assert not [c for c in app.segmented_control if (c.key or "").startswith("theme_switch")]

    open_admin(app)

    assert theme_setting(app).options == ["Light", "Dark"]       # each with its icon
    assert theme_setting(app).value == "light"
    assert not dark_style(app)


def test_choosing_dark_darkens_every_page_and_is_saved(page, tmp_path):  # noqa: F811
    runtime = make_runtime(tmp_path, [])
    app = open_admin(page(runtime=runtime))

    theme_setting(app).set_value("dark").run()
    button(app, "page_research").click().run()

    assert dark_style(app)
    assert load_app_settings(runtime.store)["theme"] == "dark"


def test_clicking_the_chosen_theme_again_keeps_it(page, tmp_path):  # noqa: F811
    runtime = make_runtime(tmp_path, [])
    app = open_admin(page(runtime=runtime))
    theme_setting(app).set_value("dark").run()

    theme_setting(app).set_value(None).run()

    assert load_app_settings(runtime.store)["theme"] == "dark"
    assert dark_style(app)


def test_the_choice_is_named_in_german(page):  # noqa: F811
    app = open_admin(page())

    language_switch(app).set_value("de").run()

    assert theme_setting(app).options == ["Hell", "Dunkel"]


def test_the_admin_s_choice_reaches_every_account(site):  # noqa: F811
    two_accounts(site)
    with patch("agent.config.ADMIN_USERNAMES", {"anna"}):
        anna = open_admin(visit_as(site, "anna"))
        theme_setting(anna).set_value("dark").run()

    assert dark_style(visit_as(site, "ben"))
