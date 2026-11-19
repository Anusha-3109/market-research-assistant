"""Tests for the language switch: EN | DE at the top right of every screen.

The app's own words are kept in two lists, one per language (ui/words). The
switch chooses the list. The choice is saved with the account.
"""

import string

import pytest
from langgraph.store.memory import InMemoryStore

from agent import memory
from tests.test_account_settings import badge, in_order
from tests.test_app import page  # noqa: F401  (page is a fixture)
from tests.test_sign_in import site  # noqa: F401  (site is a fixture)
from tests.test_two_accounts import ANNA, BEN, two_accounts, visit_as
from ui.texts import t
from ui.words import de, en


def blanks(text: str) -> set[str]:
    """The names of the blanks in a text, such as {count}."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def switch(app):
    return next(control for control in app.segmented_control if (control.key or "").startswith("language_switch"))


# --- the two lists of words ----------------------------------------------------------------------

def test_every_english_text_has_a_german_one_and_no_german_text_is_left_over():
    assert set(de.TEXTS) == set(en.TEXTS)


def test_a_german_text_has_the_same_blanks_as_the_english_one():
    assert [key for key in en.TEXTS if blanks(en.TEXTS[key]) != blanks(de.TEXTS[key])] == []


def test_no_text_is_empty():
    assert [key for texts in (en.TEXTS, de.TEXTS) for key, text in texts.items()
            if not text.strip()] == []


def test_a_text_is_given_in_the_language_asked_for():
    assert t("account.sign_out", language="en") == "Sign out"
    assert t("account.sign_out", language="de") == "Abmelden"


def test_a_language_the_app_does_not_have_gets_english():
    assert t("account.sign_out", language="fr") == "Sign out"


def test_a_text_that_does_not_exist_is_a_mistake_in_the_code():
    with pytest.raises(KeyError):
        t("no.such.text", language="en")


# --- the choice is a setting of the account ----------------------------------------------------

def test_a_new_account_starts_in_english():
    assert memory.load_settings(InMemoryStore(), ANNA)["language"] == "en"


def test_a_saved_language_comes_back_for_that_account_only():
    store = InMemoryStore()

    memory.save_settings(store, ANNA, {"language": "de"})

    assert memory.load_settings(store, ANNA)["language"] == "de"
    assert memory.load_settings(store, BEN)["language"] == "en"


def test_a_stored_language_the_app_does_not_have_falls_back_to_english():
    store = InMemoryStore()
    store.put(("users", ANNA), "settings", {"language": "fr"})

    assert memory.load_settings(store, ANNA)["language"] == "en"


# --- on the page ---------------------------------------------------------------------------------

def test_the_switch_offers_english_and_german_and_starts_on_english(page):  # noqa: F811
    app = page()

    assert not app.exception
    assert switch(app).options == ["EN", "DE"]
    assert switch(app).value == "en"


def test_choosing_german_keeps_german_on_the_next_click(page):  # noqa: F811
    app = page()

    switch(app).set_value("de").run()
    app.run()                                   # anything else that draws the page again

    assert not app.exception
    assert switch(app).value == "de"


def test_clicking_the_chosen_language_again_does_not_switch_it_off(page):  # noqa: F811
    app = page()
    switch(app).set_value("de").run()

    switch(app).set_value(None).run()

    assert switch(app).value == "de"


def test_the_switch_is_on_the_sign_in_screen_too(site):  # noqa: F811
    app = site.visit()

    assert switch(app).value == "en"
    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]     # still that screen


def test_the_account_menu_follows_the_language(site):  # noqa: F811
    two_accounts(site)
    app = visit_as(site, "anna")
    assert any("Signed in as" in text for text in in_order(badge(app)))

    switch(app).set_value("de").run()

    inside = in_order(badge(app))
    assert any('Angemeldet als <span class="gw-account-name">Anna</span>' in text for text in inside)
    assert "Abmelden" in inside and "Sign out" not in inside


def test_the_language_an_account_chose_is_there_at_its_next_sign_in(site):  # noqa: F811
    two_accounts(site)
    switch(visit_as(site, "anna")).set_value("de").run()

    again = visit_as(site, "anna")

    assert not again.exception
    assert switch(again).value == "de"
    assert "Abmelden" in in_order(badge(again))


def test_one_accounts_language_does_not_reach_another_account(site):  # noqa: F811
    two_accounts(site)
    switch(visit_as(site, "anna")).set_value("de").run()

    assert switch(visit_as(site, "ben")).value == "en"


def test_signing_out_goes_back_to_english_for_the_next_person(site):  # noqa: F811
    two_accounts(site)
    app = visit_as(site, "anna")
    switch(app).set_value("de").run()

    next(b for b in app.button if b.key == "sign_out").click().run()

    assert switch(app).value == "en"
