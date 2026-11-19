"""Tests for German on the screens around a conversation: the start screen,
the pickers behind its cards, the "How it works" guide, the approval forms
and the sign-in screen. Also: a German country name counts as naming the
country.

A choice keeps its English value underneath: a picked chip is still "Oat
milk", and the card still opens the picker it opened before.
"""

from langchain_core.messages import AIMessage, HumanMessage

from agent.agent import country_came_from_user
from tests.test_app import SAVE_CALL, button, page  # noqa: F401  (page is a fixture)
from tests.test_language import switch
from tests.test_sign_in import site  # noqa: F401  (site is a fixture)
from ui.picker import CATALOGUE, COUNTRIES, INDUSTRIES, PICKERS, chip_name, sentence_for


def german(app):
    switch(app).set_value("de").run()
    assert not app.exception
    return app


def html(app) -> str:
    return "\n".join(element.proto.body for element in app.get("html"))


def labels(app) -> list[str]:
    return [b.label for b in app.button]


# --- a German country name ---------------------------------------------------------------------

def test_a_country_named_in_german_counts_as_named_by_the_user():
    said = [HumanMessage("Hafermilch in Österreich, bitte")]

    assert country_came_from_user("Austria", said, saved_region="")
    assert country_came_from_user("Netherlands", [HumanMessage("Kaffee in den Niederlanden")], "")
    assert country_came_from_user("Switzerland", [HumanMessage("Land: Schweiz")], "")


def test_a_country_nobody_named_is_still_refused():
    assert not country_came_from_user("Austria", [HumanMessage("Hafermilch in Frankreich")], "")


# --- the start screen ------------------------------------------------------------------------------

def test_the_start_screen_is_in_german(page):  # noqa: F811
    app = german(page())

    assert "Erforschen Sie **jeden Markt**." in [t.value for t in app.title]
    assert "**Bericht schreiben**\n\nGesunde Essenslieferung in Deutschland" in labels(app)
    assert "So funktioniert **Markavi**." in labels(app)


def test_a_german_card_opens_the_same_picker(page):  # noqa: F811
    app = german(page())

    button(app, "card_0").click().run()

    assert not app.exception
    assert "Einen **Bericht** schreiben." in [t.value for t in app.title]
    assert button(app, "picker_go").label == "Recherchieren"
    assert button(app, "picker_back").label == "Zurück zum Start"


# --- the pickers -------------------------------------------------------------------------------

def test_every_chip_has_a_german_name():
    names = [name for industry in CATALOGUE for group in (industry.products, industry.companies, industry.ideas)
             for _, name in group] + [name for _, name in COUNTRIES] + [name for _, name in INDUSTRIES] \
        + [industry.name for industry in CATALOGUE]
    companies = {name for industry in CATALOGUE for _, name in industry.companies}
    untranslated = [name for name in names if name not in companies and chip_name(name, "de") == name]
    assert untranslated == []


def test_a_company_keeps_its_own_name():
    assert chip_name("HelloFresh", "de") == "HelloFresh"


def test_every_picker_has_a_german_sentence():
    picks = {"product": "Oat milk", "country": "Austria", "company": "Oatly", "idea": "Vegan bakery",
             "industry": "Fashion"}
    for card in PICKERS:
        assert sentence_for(card, picks, "de"), card


def test_picked_chips_make_a_german_question():
    picks = {"product": "Oat milk", "country": "Austria"}

    assert sentence_for("Write a report", picks, "de") == \
        "Erstellen Sie einen Marktforschungsbericht. Produkt: Hafermilch. Land: Österreich."
    assert sentence_for("Write a report", picks, "en") == \
        "Give me a market research report for oat milk in Austria."


def test_clicking_chips_in_german_fills_the_box_in_german(page):  # noqa: F811
    app = german(page())
    button(app, "card_0").click().run()

    product = next(b for b in app.button if b.key == "pick_product_1")
    assert product.label == "Hafermilch +"
    product.click().run()
    next(b for b in app.button if b.key == "pick_country_7").click().run()

    assert app.text_input(key="picker_text").value == \
        "Erstellen Sie einen Marktforschungsbericht. Produkt: Hafermilch. Land: Österreich."


def test_the_industry_row_and_the_hint_are_in_german(page):  # noqa: F811
    app = german(page())
    button(app, "card_0").click().run()
    next(b for b in app.button if b.key == "pick_product_1").click().run()

    captions = [c.value for c in app.caption]
    assert "BRANCHE WÄHLEN" in captions and "DANN EIN PRODUKT" in captions
    assert "Wählen Sie jetzt ein Land." in captions
    assert next(b for b in app.button if b.key == "field_0").label == "Essen und Trinken"


# --- the guide ----------------------------------------------------------------------------------

def test_the_guide_is_in_german(page):  # noqa: F811
    app = german(page())

    button(app, "learn").click().run()

    assert not app.exception
    assert "Wie funktioniert Markavi?" in html(app)
    assert '<div class="gw-step-title">Wettbewerber finden</div>' in html(app) or \
        "Wettbewerber finden" in html(app)
    assert "Markavi arbeitet in einem festen Ablauf aus fünf Schritten." in \
        "\n".join(m.value for m in app.markdown)
    assert "GUT ZU WISSEN" in [c.value for c in app.caption]
    assert button(app, "chip_try").label == "Ausprobieren: gesunde Essenslieferung in Deutschland"


# --- the approval forms ------------------------------------------------------------------------

def test_the_save_form_is_in_german(page):  # noqa: F811
    app = german(page([SAVE_CALL, AIMessage("Gespeichert.")]))

    app.chat_input[0].set_value("Speichern Sie diesen Bericht.").run()

    assert not app.exception
    assert app.text_input[0].label == "Titel"
    assert "**Diesen Bericht in einer Datei speichern?**" in [m.value for m in app.markdown]
    assert [b.label for b in app.button if (b.key or "").startswith("FormSubmitter:save_form")] == \
        ["Speichern", "Nicht speichern"]


# --- the sign-in screen ------------------------------------------------------------------------

def test_the_sign_in_screen_is_in_german(site):  # noqa: F811
    app = german(site.visit())

    assert [tab.label for tab in app.tabs] == ["Anmelden", "Konto erstellen"]
    assert app.text_input(key="sign_in_username").label == "Benutzername"
    assert "Passwort ändern" in labels(app)


def test_a_wrong_password_is_explained_in_german(site):  # noqa: F811
    app = german(site.visit())

    app.text_input(key="sign_in_username").set_value("nobody")
    app.text_input(key="sign_in_password").set_value("wrong-password")
    next(b for b in app.button if b.label == "Anmelden").click().run()

    assert [e.value for e in app.error] == \
        ["Benutzername und Passwort passen nicht zusammen. Versuchen Sie es noch einmal."]


def test_in_english_the_sign_in_screen_reads_as_before(site):  # noqa: F811
    app = site.visit()

    assert [tab.label for tab in app.tabs] == ["Sign in", "Create account"]
