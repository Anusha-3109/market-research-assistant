"""Tests for the picker screens behind the start cards.

The first part checks the plain logic: which sentence the chips build. The
second part runs the page without a browser and clicks through a picker.
"""

import pytest
from langchain_core.messages import AIMessage

from tests.test_app import button, page, texts  # noqa: F401  (page is a fixture)
from ui import picker
from ui.picker import PICKERS, in_a_sentence, missing_hint, sentence, toggle
from ui.start import EXAMPLES


# --- which sentence the chips build -----------------------------------------------------------

def test_every_start_card_has_a_picker():
    assert {title for _, title, _, _ in EXAMPLES} == set(PICKERS)


def test_a_product_and_a_country_become_a_report_request():
    built = sentence(PICKERS["Write a report"], {"product": "Oat milk", "country": "Germany"})

    assert built == "Give me a market research report for oat milk in Germany."


def test_each_card_builds_its_own_kind_of_question():
    market = {"product": "Pet food", "country": "Netherlands"}

    assert sentence(PICKERS["Check demand"], market) == \
        "Is interest in pet food rising in the Netherlands?"
    assert sentence(PICKERS["Follow the news"], market) == \
        "What has changed recently in the pet food market in the Netherlands?"
    assert sentence(PICKERS["Find competitors"], market) == \
        "Who are the main companies selling pet food in the Netherlands?"
    assert sentence(PICKERS["Size a market"], market) == \
        "How big is the pet food market in the Netherlands?"
    assert sentence(PICKERS["Research a company"], {"company": "HelloFresh"}) == \
        "How big is HelloFresh? Give me its revenue and number of employees."
    assert sentence(PICKERS["Compare prices"], {"company": "Prepmymeal"}) == \
        "What does Prepmymeal charge?"
    assert sentence(PICKERS["Test my idea"], {"idea": "Vegan bakery", "country": "Spain"}) == \
        "I want to open a vegan bakery in Spain. Give me a market research report."
    assert sentence(PICKERS["Set your market"],
                    {"country": "Germany", "industry": "Meal delivery"}) == \
        "I am based in Germany and I work in meal delivery."


def test_no_sentence_until_every_row_has_a_pick():
    report = PICKERS["Write a report"]

    assert sentence(report, {}) is None
    assert sentence(report, {"product": "Oat milk"}) is None
    assert sentence(report, {"country": "Germany"}) is None


def test_names_are_adjusted_to_read_well_in_a_sentence():
    assert in_a_sentence("product", "Oat milk") == "oat milk"
    assert in_a_sentence("country", "United Kingdom") == "the United Kingdom"
    assert in_a_sentence("country", "France") == "France"
    assert in_a_sentence("idea", "Online skincare brand") == "an online skincare brand"
    assert in_a_sentence("idea", "Vegan bakery") == "a vegan bakery"
    assert in_a_sentence("company", "REWE") == "REWE"          # names are not changed


def test_one_chip_per_row_and_a_second_click_takes_it_back():
    picks = toggle({}, "product", "Oat milk")
    assert picks == {"product": "Oat milk"}

    picks = toggle(picks, "product", "Pet food")                # another chip replaces it
    assert picks == {"product": "Pet food"}

    assert toggle(picks, "product", "Pet food") == {}           # the same chip again clears it


def test_the_hint_names_the_row_that_is_still_missing():
    report = PICKERS["Write a report"]

    assert missing_hint(report, {}) == ""                       # nothing picked: no nagging
    assert missing_hint(report, {"product": "Oat milk"}) == "Now pick a country."
    assert missing_hint(report, {"country": "Germany"}) == "Now pick a product."
    assert missing_hint(report, {"product": "Oat milk", "country": "Germany"}) == ""


# --- the chips, grouped by industry ---------------------------------------------------------

def test_each_industry_has_its_own_products_companies_and_ideas():
    food = picker.chips("product", "Food and drink")
    beauty = picker.chips("product", "Beauty and skincare")

    assert ("Oat milk" in [name for _, name in food])
    assert ("Sunscreen" in [name for _, name in beauty])
    assert not {name for _, name in food} & {name for _, name in beauty}
    assert "Nivea" in [name for _, name in picker.chips("company", "Beauty and skincare")]
    assert "Dog daycare" in [name for _, name in picker.chips("idea", "Pet care")]


def test_countries_are_the_same_for_every_industry():
    assert picker.chips("country", "Pet care") == picker.chips("country", "Fashion")


@pytest.mark.parametrize("industry", [industry.name for industry in picker.CATALOGUE])
def test_every_industry_offers_enough_of_each_kind(industry):
    assert len(picker.chips("product", industry)) >= 8
    assert len(picker.chips("company", industry)) >= 8
    assert len(picker.chips("idea", industry)) >= 4


@pytest.mark.parametrize("industry", [industry.name for industry in picker.CATALOGUE])
@pytest.mark.parametrize("group", ["product", "company", "idea", "country", "industry"])
def test_chip_names_are_unique_within_a_row(industry, group):
    names = [name for _, name in picker.chips(group, industry)]

    assert len(names) == len(set(names))


def test_changing_industry_drops_its_picks_but_keeps_the_country():
    state = {"industry": "Food and drink",
             "picks": {"product": "Oat milk", "country": "Germany"}}

    picker.change_industry(state, "Pet care")

    assert state["industry"] == "Pet care"
    assert state["picks"] == {"country": "Germany"}


def test_choosing_the_same_industry_again_changes_nothing():
    state = {"industry": "Food and drink", "picks": {"product": "Oat milk"}}

    picker.change_industry(state, "Food and drink")

    assert state["picks"] == {"product": "Oat milk"}


def test_only_pickers_with_products_companies_or_ideas_show_the_industry_row():
    assert picker.uses_industry(PICKERS["Write a report"])
    assert picker.uses_industry(PICKERS["Compare prices"])
    assert picker.uses_industry(PICKERS["Test my idea"])
    assert not picker.uses_industry(PICKERS["Set your market"])


def test_company_logo_styles_cover_every_company_and_carry_a_letter_fallback():
    companies = picker.chips("company", "Fashion")

    styles = picker.logo_styles(companies)

    for index, (site, _) in enumerate(companies):
        assert f".st-key-pick_company_{index} " in styles
        assert f"https://{site}/favicon.ico" in styles
    assert styles.count("data:image/svg+xml") == len(companies)


# --- clicking through a picker on the page -------------------------------------------------------

def open_card(app, title: str):
    index = [card_title for _, card_title, _, _ in EXAMPLES].index(title)
    return button(app, f"card_{index}").click().run()


def test_a_card_opens_its_picker_without_calling_the_model(page):
    app = page([])                      # no replies: the model must not be needed

    open_card(app, "Check demand")

    assert not app.exception
    assert app.title[0].value == "Check **demand**."
    assert app.text_input[0].value == ""
    assert not [b for b in app.button if (b.key or "").startswith("card_")]
    assert len(app.chat_input) == 0     # the picker's own box replaces it


def test_picking_a_product_and_a_country_fills_the_box(page):
    app = page([])
    open_card(app, "Check demand")

    button(app, "pick_product_1").click().run()                 # Oat milk
    assert app.text_input[0].value == ""                        # one row is not enough
    assert "Now pick a country." in texts(app)

    button(app, "pick_country_0").click().run()                 # Germany

    assert app.text_input[0].value == "Is interest in oat milk rising in Germany?"
    assert button(app, "pick_product_1").proto.type == "primary"   # shown as chosen


def test_research_sends_the_sentence_in_the_box(page):
    app = page([AIMessage("Interest is rising.")])
    open_card(app, "Check demand")
    button(app, "pick_product_1").click().run()
    button(app, "pick_country_0").click().run()

    button(app, "picker_go").click().run()

    assert not app.exception
    shown = texts(app)
    assert "Is interest in oat milk rising in Germany?" in shown
    assert "Interest is rising." in shown
    assert "picker" not in app.session_state                    # the picker is closed


def test_typing_your_own_words_works_without_any_chip(page):
    app = page([AIMessage("About 4%.")])
    open_card(app, "Size a market")

    app.text_input[0].set_value("How big is the kombucha market in Austria?")
    button(app, "picker_go").click().run()

    assert "How big is the kombucha market in Austria?" in texts(app)
    assert "About 4%." in texts(app)


def test_research_with_an_empty_box_asks_for_input_and_sends_nothing(page):
    app = page([])                      # a call to the model would fail the test
    open_card(app, "Write a report")

    button(app, "picker_go").click().run()

    assert not app.exception
    assert app.warning[0].value == "Pick the chips or type your own words first."
    assert app.title[0].value == "Write a **report**."          # still on the picker


def test_back_to_start_returns_to_the_cards(page):
    app = page([])
    open_card(app, "Research a company")

    button(app, "picker_back").click().run()

    assert app.title[0].value == "Research **any market**."
    assert len([b for b in app.button if (b.key or "").startswith("card_")]) == 9
    assert len(app.chat_input) == 1


def test_a_company_chip_fills_the_box_at_once(page):
    app = page([])
    open_card(app, "Compare prices")

    button(app, "pick_company_1").click().run()                 # Prepmymeal

    assert app.text_input[0].value == "What does Prepmymeal charge?"


def test_set_your_market_has_a_save_button(page):
    app = page([])

    open_card(app, "Set your market")

    assert button(app, "picker_go").label == "Save"


def test_choosing_an_industry_swaps_the_product_chips(page):
    app = page([])
    open_card(app, "Write a report")
    assert button(app, "pick_product_1").label == "Oat milk +"

    button(app, "field_2").click().run()                        # Pet care

    assert not app.exception
    assert button(app, "pick_product_0").label == "Pet food +"
    assert button(app, "field_2").proto.type == "primary"


def test_a_pick_from_another_industry_builds_its_own_sentence(page):
    app = page([])
    open_card(app, "Compare prices")

    button(app, "field_1").click().run()                        # Beauty and skincare
    button(app, "pick_company_1").click().run()                 # Nivea

    assert app.text_input[0].value == "What does Nivea charge?"


def test_set_your_market_has_no_industry_row_of_its_own(page):
    app = page([])

    open_card(app, "Set your market")

    assert not [b for b in app.button if (b.key or "").startswith("field_")]
