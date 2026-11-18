"""Tests for the formats of a report: the full report, and the investor
one-pager laid out from the same findings.

The one-pager is put together by code from the figures kept with a report.
No model is asked, so it holds nothing the report did not find.
"""

from langchain_core.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

from agent.citations import Source
from agent.report.formats import one_pager
from agent.report.snapshot import build_snapshot
from tests.test_app import APP, make_runtime, page, texts  # noqa: F401  (page is a fixture)
from tests.test_snapshot import final_state

REPORT = ("# Market research report: oat milk in Germany\n\n## 1. Market overview\n\n"
          "- Oat milk market value: 1 billion EUR (Germany, 2025). [source](https://a.example/m)\n")
SOURCES = [Source(1, "Oat milk in Germany", "a.example", "https://a.example/m"),
           Source(2, "Oatly shop", "oatly.example", "https://oatly.example/shop", official=True)]


def page_text(snapshot=None, sources=SOURCES) -> str:
    return one_pager("Oat milk in Germany", snapshot or build_snapshot(final_state()), sources)


# --- what the one-pager holds ---------------------------------------------------------------------

def test_the_one_pager_starts_with_the_title_and_says_what_it_is():
    lines = page_text().splitlines()

    assert lines[0] == "# Oat milk in Germany"
    assert "Investor one-pager · 2 sources" in lines[2]


def test_the_figures_are_listed_with_where_and_when_they_apply():
    text = page_text()

    assert "- Oat milk market value: **1 billion EUR** (Germany, 2025)" in text
    assert "- Growth a year: **8%** (Germany, 2026-2030)" in text
    assert "- Competitors confirmed: **2** of 5 candidates" in text


def test_a_converted_amount_follows_its_figure():
    snapshot = build_snapshot(final_state())
    snapshot["figures"][0].update(
        value="USD 1.1 billion",
        converted="about EUR 1 billion, converted at the ECB rate of 18 Nov 2026")

    assert ("- Oat milk market value: **USD 1.1 billion** (Germany, 2025); "
            "about EUR 1 billion, converted at the ECB rate of 18 Nov 2026") in page_text(snapshot)


def test_each_competitor_is_one_line_with_its_offer_size_and_price():
    text = page_text()

    assert ("- **Oatly**: Oat drinks in six varieties. Size: Revenue: 783 million USD; "
            "Employees: 1,500. Price: 2.49 EUR (Barista 1 l).") in text
    # What was not found is said, not left out.
    assert "- **Alpro**: Plant-based drinks. Size: not found. Price: not found." in text


def test_demand_opportunities_and_risks_come_from_the_trend_and_the_swot():
    text = page_text()

    assert '- Search interest for "Hafermilch": rising (+32%)' in text
    assert "## Opportunities\n\n- Barista editions grow fastest\n- Private label is thin" in text
    assert "## Risks\n\n- t" in text


def test_the_sources_are_numbered_as_in_the_report():
    text = page_text()

    assert "1. [Oat milk in Germany](https://a.example/m) (a.example)" in text
    assert "2. [Oatly shop](https://oatly.example/shop) (oatly.example)" in text


def test_a_part_with_nothing_to_show_is_left_out():
    snapshot = build_snapshot(final_state())
    snapshot.update(trend=None, opportunities=[], threats=[], competitors=[])

    text = page_text(snapshot, sources=[])

    for heading in ("## Competitors", "## Demand", "## Opportunities", "## Risks", "## Sources"):
        assert heading not in text
    assert "## Key figures" in text


def test_a_snapshot_saved_before_risks_were_kept_still_makes_a_page():
    snapshot = build_snapshot(final_state())
    del snapshot["threats"]

    assert "## Risks" not in page_text(snapshot)


def test_the_snapshot_keeps_the_threats_of_the_swot():
    assert build_snapshot(final_state())["threats"] == ["t"]


# --- on the page ---------------------------------------------------------------------------------

def open_report(page, tmp_path, with_snapshot=True):  # noqa: F811
    runtime = make_runtime(tmp_path, [])
    wants = AIMessage("", tool_calls=[{"name": "create_market_report", "id": "r1",
                                       "args": {"product": "oat milk", "country": "Germany"}}])
    details = {"problems": [], "log": []}
    if with_snapshot:
        details["snapshot"] = build_snapshot(final_state())
    result = ToolMessage(REPORT, tool_call_id="r1", name="create_market_report", artifact=details)
    runtime.agent.update_state({"configurable": {"thread_id": "fmt"}}, {"messages": [
        {"role": "user", "content": "A report on oat milk in Germany"}, wants, result]},
        as_node="tools")
    page(runtime=runtime)
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["c"] = "fmt"
    app.run()
    next(b for b in app.sidebar.button if b.key == "view_report").click().run()
    return app


def format_picker(app):
    return next((box for box in app.selectbox if box.label == "Format"), None)


def section_cards(app) -> list[str]:
    return [element.proto.body for element in app.get("html")
            if 'class="gw-section-title"' in element.proto.body]


def test_the_report_view_offers_the_formats_and_opens_on_the_full_report(page, tmp_path):  # noqa: F811
    app = open_report(page, tmp_path)

    assert not app.exception
    assert format_picker(app).options == ["Full market report", "Investor one-pager",
                                          "Pitch deck slides"]
    assert format_picker(app).value == "Full market report"
    assert len(section_cards(app)) == 1


def test_choosing_the_one_pager_shows_it_in_place_of_the_section_cards(page, tmp_path):  # noqa: F811
    app = open_report(page, tmp_path)

    format_picker(app).set_value("Investor one-pager").run()

    assert not app.exception
    shown = texts(app)
    assert "Investor one-pager" in shown
    assert "Barista editions grow fastest" in shown and "**Oatly**" in shown
    assert section_cards(app) == []
    assert [b.label for b in app.get("download_button")] == ["Markdown", "PDF"]


def test_a_report_without_saved_figures_has_only_the_full_report(page, tmp_path):  # noqa: F811
    app = open_report(page, tmp_path, with_snapshot=False)

    assert format_picker(app) is None
    assert len(section_cards(app)) == 1
