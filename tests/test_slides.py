"""Tests for the pitch deck: a report as a handful of slides, shown in the
app and downloadable as a PowerPoint file.

Like the one-pager, the slides are laid out by code from the figures kept
with a report. No model is asked.
"""

from io import BytesIO

from pptx import Presentation

from agent.pptx_export import slides_to_pptx
from agent.report.formats import SLIDES, slides
from agent.report.snapshot import build_snapshot
from tests.test_app import page, texts  # noqa: F401  (page is a fixture)
from tests.test_formats import SOURCES, format_picker, open_report
from tests.test_snapshot import final_state


def deck(snapshot=None, sources=SOURCES):
    return slides("Oat milk in Germany", snapshot or build_snapshot(final_state()), sources)


# --- what the slides hold -------------------------------------------------------------------------

def test_a_full_report_makes_seven_slides_in_a_fixed_order():
    assert [slide.title for slide in deck()] == [
        "Oat milk in Germany", "The market", "Competitors", "Prices", "Demand",
        "Opportunities and risks", "Sources"]


def test_the_first_slide_says_what_the_deck_is():
    first = deck()[0]

    assert first.bullets == ["Market research · 2 sources"]


def test_the_market_slide_lists_the_figures_with_where_and_when():
    market = deck()[1]

    assert market.bullets[0] == "Oat milk market value: 1 billion EUR (Germany, 2025)"
    assert market.bullets[-1] == "Competitors confirmed: 2 of 5 candidates"


def test_competitors_and_prices_are_two_slides_and_say_what_was_not_found():
    competitors, prices = deck()[2], deck()[3]

    assert competitors.bullets == ["Oatly: Oat drinks in six varieties", "Alpro: Plant-based drinks"]
    assert prices.bullets == ["Oatly: 2.49 EUR (Barista 1 l)", "Alpro: not found"]


def test_the_demand_slide_carries_the_direction_and_the_bars_of_the_chart():
    demand = deck()[4]

    assert demand.bullets == ['Search interest for "Hafermilch": rising (+32%)']
    assert len(demand.bars) == 12
    assert demand.bars[0] == ("2026-01-01", 5.0)


def test_opportunities_and_risks_are_marked_on_one_slide():
    outlook = deck()[5]

    assert outlook.bullets == ["Opportunity: Barista editions grow fastest",
                               "Opportunity: Private label is thin", "Risk: t"]


def test_the_last_slide_numbers_the_sources():
    assert deck()[-1].numbered
    assert deck()[-1].bullets == ["1. Oat milk in Germany (a.example)", "2. Oatly shop (oatly.example)"]


def test_a_slide_with_nothing_to_show_is_left_out():
    snapshot = build_snapshot(final_state())
    snapshot.update(trend=None, opportunities=[], threats=[], competitors=[])

    assert [slide.title for slide in deck(snapshot, sources=[])] == ["Oat milk in Germany", "The market"]


def test_a_long_line_is_cut_so_that_it_fits_a_slide():
    snapshot = build_snapshot(final_state())
    snapshot["opportunities"] = ["word " * 80]

    longest = max(len(bullet) for bullet in deck(snapshot)[5].bullets)

    assert longest <= 181 and deck(snapshot)[5].bullets[0].endswith("…")


# --- the PowerPoint file ----------------------------------------------------------------------------

def reopened(snapshot=None):
    return Presentation(BytesIO(slides_to_pptx(deck(snapshot))))


def test_the_file_is_a_powerpoint_with_one_page_per_slide():
    data = slides_to_pptx(deck())

    assert data[:2] == b"PK"                                  # a .pptx is a zip file
    assert len(reopened().slides) == 7


def test_each_page_has_its_title_and_its_lines():
    pages = list(reopened().slides)

    words = ["\n".join(shape.text_frame.text for shape in page.shapes if shape.has_text_frame)
             for page in pages]
    assert "Oat milk in Germany" in words[0]
    assert "The market" in words[1] and "Oat milk market value: 1 billion EUR (Germany, 2025)" in words[1]
    assert "Alpro: not found" in words[3]


def test_the_demand_page_has_a_chart_with_the_measurements():
    demand = list(reopened().slides)[4]

    charts = [shape.chart for shape in demand.shapes if shape.has_chart]
    assert len(charts) == 1
    assert list(charts[0].plots[0].series[0].values)[:2] == [5.0, 10.0]


def test_the_pages_are_wide_screen():
    deck_file = reopened()

    assert round(deck_file.slide_width / deck_file.slide_height, 2) == 1.78       # 16 to 9


# --- on the page ---------------------------------------------------------------------------------

def slide_cards(app) -> list[str]:
    return [element.proto.body for element in app.get("html")
            if 'class="gw-slide' in element.proto.body]


def test_the_picker_offers_the_slides_as_a_third_format(page, tmp_path):  # noqa: F811
    app = open_report(page, tmp_path)

    assert format_picker(app).options == ["Full market report", "Investor one-pager", SLIDES]


def test_choosing_the_slides_shows_them_and_offers_a_powerpoint_download(page, tmp_path):  # noqa: F811
    app = open_report(page, tmp_path)

    format_picker(app).set_value(SLIDES).run()

    assert not app.exception
    cards = "\n".join(slide_cards(app))
    assert cards.count('class="gw-slide-title"') == 7
    assert "Alpro: not found" in cards and "The market" in cards
    assert [b.label for b in app.get("download_button")] == ["PowerPoint"]


def test_words_on_a_slide_are_shown_as_text_never_as_markup(page, tmp_path):  # noqa: F811
    app = open_report(page, tmp_path)
    app.runtime = None
    format_picker(app).set_value(SLIDES).run()

    assert "<script" not in "\n".join(slide_cards(app))
