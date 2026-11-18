"""Tests for the Snapshot view: the key figures of a report at a glance.

The figures come from what the report workflow found, kept as separate
values next to the report text. The page is run without a browser.
"""

import json

from langchain_core.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

from agent.report.snapshot import build_snapshot, trend_bars
from agent.report.state import (
    Competitor,
    CompetitorProfile,
    MarketFigure,
    PricePoint,
    Rejection,
    Swot,
    TrendResult,
)
from tests.test_app import APP, button, make_runtime, page, texts  # noqa: F401  (page is a fixture)

REPORT = "# Market research report: oat milk in Germany\n\n## 1. Market overview\n\n- A fact."


def figure(statement, value, scope="country", year="2025", url="https://a.example/m"):
    return MarketFigure(statement=statement, value=value, area="Germany", scope=scope,
                        year=year, source_url=url)


def final_state() -> dict:
    """What the workflow holds when a report is finished."""
    return {
        "product": "oat milk", "country": "Germany",
        "market_figures": [
            figure("Plant milk market, Europe", "3 billion EUR", scope="region"),
            figure("Oat milk market value", "1 billion EUR"),
            figure("Growth a year", "8%", year="2026-2030", url="https://b.example/g"),
            figure("Households buying", "24%"),
            figure("Litres sold", "310 million"),
            figure("Shops stocking it", "92%"),
        ],
        "competitors": [
            Competitor(name="Oatly", shop_url="https://oatly.example", evidence_url="https://e.example",
                       reason="sells it", offer="Oat drinks in six varieties"),
            Competitor(name="Alpro", shop_url="https://alpro.example", evidence_url="https://e.example",
                       reason="sells it", offer="Plant-based drinks"),
        ],
        "rejected": [Rejection(name="Milka", reason="chocolate"),
                     Rejection(name="Arla", reason="dairy"),
                     Rejection(name="Bauer", reason="dairy")],
        "profiles": [
            CompetitorProfile(name="Oatly", shop_url="https://oatly.example",
                              figures="Revenue: 783 million USD\nEmployees: 1,500",
                              figures_source="https://f.example",
                              prices=[PricePoint(product="Barista 1 l", price="2.49 EUR"),
                                      PricePoint(product="Organic 1 l", price="2.29 EUR")],
                              price_source="https://oatly.example/shop", price_note=""),
            CompetitorProfile(name="Alpro", shop_url="https://alpro.example", figures="",
                              figures_source="", prices=[], price_source="",
                              price_note="The shop page shows no prices."),
        ],
        "trend": TrendResult(term="Hafermilch", summary="Search interest\nDirection: rising (+32%)",
                             reliable=True, unit="search interest, 0 to 100",
                             points=[(f"2026-{month:02d}-01", float(month * 5)) for month in range(1, 13)]),
        "swot": Swot(strengths=["s"], weaknesses=["w"],
                     opportunities=["Barista editions grow fastest", "Private label is thin"],
                     threats=["t"]),
    }


# --- what is kept ----------------------------------------------------------------------------------

def test_the_snapshot_keeps_up_to_four_figures_with_the_countrys_own_first():
    figures = build_snapshot(final_state())["figures"]

    assert [f["label"] for f in figures] == ["Oat milk market value", "Growth a year",
                                             "Households buying", "Litres sold"]
    assert figures[0] == {"label": "Oat milk market value", "value": "1 billion EUR",
                          "note": "Germany, 2025", "url": "https://a.example/m",
                          "converted": ""}          # already in the country's own currency
    assert figures[1]["note"] == "Germany, 2026-2030"


def test_a_figure_in_a_foreign_currency_keeps_its_value_and_gets_a_converted_one():
    from unittest.mock import patch

    state = final_state()
    state["market_figures"] = [figure("Oat milk market value", "USD 0.3 billion")]

    with patch("agent.currency.real_rate", lambda source, target: (0.93, "2026-11-18")):
        [kept] = build_snapshot(state)["figures"]

    assert kept["value"] == "USD 0.3 billion"            # as the source wrote it
    assert kept["converted"] == "about EUR 279 million, converted at the ECB rate of 18 Nov 2026"


def test_figures_for_a_wider_area_fill_in_when_the_country_has_few():
    state = final_state()
    state["market_figures"] = state["market_figures"][:2]

    assert [f["label"] for f in build_snapshot(state)["figures"]] == \
        ["Oat milk market value", "Plant milk market, Europe"]


def test_each_competitor_keeps_its_offer_its_size_and_one_price():
    oatly, alpro = build_snapshot(final_state())["competitors"]

    assert oatly == {"name": "Oatly", "offer": "Oat drinks in six varieties",
                     "size": "Revenue: 783 million USD; Employees: 1,500",
                     "price": "2.49 EUR (Barista 1 l)", "site": "https://oatly.example"}
    assert alpro["size"] == "not found"
    assert alpro["price"] == "not found"


def test_the_snapshot_counts_confirmed_competitors_and_all_candidates():
    snapshot = build_snapshot(final_state())

    assert (snapshot["confirmed"], snapshot["candidates"]) == (2, 5)


def test_the_trend_keeps_its_word_its_direction_and_its_points():
    trend = build_snapshot(final_state())["trend"]

    assert trend["term"] == "Hafermilch"
    assert trend["direction"] == "rising (+32%)"
    assert trend["reliable"] is True
    assert trend["points"][0] == ["2026-01-01", 5.0] and len(trend["points"]) == 12


def test_a_report_without_a_trend_or_a_swot_has_none_in_its_snapshot():
    state = final_state()
    state["trend"], state["swot"] = None, None

    snapshot = build_snapshot(state)

    assert snapshot["trend"] is None
    assert snapshot["opportunities"] == []


def test_the_opportunities_come_from_the_swot():
    assert build_snapshot(final_state())["opportunities"] == \
        ["Barista editions grow fastest", "Private label is thin"]


def test_the_snapshot_is_plain_data_that_can_be_saved():
    assert json.loads(json.dumps(build_snapshot(final_state())))["confirmed"] == 2


# --- the bars of the chart -----------------------------------------------------------------------

def test_many_points_are_averaged_into_at_most_twelve_bars():
    points = [[f"day {number}", float(number)] for number in range(1, 49)]    # 48 points

    bars = trend_bars(points)

    assert len(bars) == 12
    assert bars[0] == ("day 1", 2.5)            # the average of 1, 2, 3, 4
    assert bars[-1] == ("day 45", 46.5)


def test_a_few_points_are_one_bar_each():
    assert trend_bars([["a", 1.0], ["b", 3.0]]) == [("a", 1.0), ("b", 3.0)]
    assert trend_bars([]) == []


# --- on the page ---------------------------------------------------------------------------------

def with_snapshot(page, tmp_path, snapshot=None, replies=None):  # noqa: F811
    """The page opened at a conversation that holds a report with a
    snapshot."""
    runtime = make_runtime(tmp_path, replies or [])
    wants = AIMessage("", tool_calls=[{"name": "create_market_report", "id": "r1",
                                       "args": {"product": "oat milk", "country": "Germany"}}])
    details = {"problems": [], "log": [], "snapshot": snapshot or build_snapshot(final_state())}
    result = ToolMessage(REPORT, tool_call_id="r1", name="create_market_report", artifact=details)
    runtime.agent.update_state({"configurable": {"thread_id": "snap"}}, {"messages": [
        {"role": "user", "content": "A report on oat milk in Germany"}, wants, result]},
        as_node="tools")
    page(runtime=runtime)
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["c"] = "snap"
    return app.run()


def view_links(app) -> list[str]:
    return [b.label for b in app.sidebar.button if (b.key or "").startswith("view_")]


def snapshot_html(app) -> str:
    return "\n".join(element.proto.body for element in app.get("html")
                     if 'class="gw-snap' in element.proto.body)


def test_a_report_with_a_snapshot_opens_on_it(page, tmp_path):  # noqa: F811
    app = with_snapshot(page, tmp_path)

    assert not app.exception
    assert view_links(app) == ["Snapshot", "Ask", "Report"]
    assert button(app, "view_snapshot").proto.type == "secondary"
    assert len(app.chat_input) == 0                # questions are asked in the Ask view


def test_the_snapshot_shows_the_figures_the_competitors_and_the_opportunities(page, tmp_path):  # noqa: F811
    shown = snapshot_html(with_snapshot(page, tmp_path))

    assert "1 billion EUR" in shown and "Oat milk market value" in shown
    assert "Germany, 2025" in shown
    assert "Competitors confirmed" in shown and "of 5 candidates" in shown
    assert "Oatly" in shown and "2.49 EUR (Barista 1 l)" in shown
    assert "Barista editions grow fastest" in shown
    assert "Hafermilch" in shown and "rising (+32%)" in shown


def test_words_from_the_web_are_shown_as_text_never_as_markup(page, tmp_path):  # noqa: F811
    snapshot = build_snapshot(final_state())
    snapshot["competitors"][0]["name"] = "<b>Oatly</b>"
    snapshot["figures"][0]["url"] = 'javascript:alert(1)'

    shown = snapshot_html(with_snapshot(page, tmp_path, snapshot=snapshot))

    assert "&lt;b&gt;Oatly&lt;/b&gt;" in shown and "<b>Oatly</b>" not in shown
    assert "javascript:" not in shown              # only web addresses become links


def test_a_converted_value_is_shown_under_its_figure(page, tmp_path):  # noqa: F811
    snapshot = build_snapshot(final_state())
    snapshot["figures"][0].update(
        value="USD 0.3 billion",
        converted="about EUR 279 million, converted at the ECB rate of 18 Nov 2026")

    shown = snapshot_html(with_snapshot(page, tmp_path, snapshot=snapshot))

    assert "USD 0.3 billion" in shown
    assert "about EUR 279 million, converted at the ECB rate of 18 Nov 2026" in shown
    assert shown.count("gw-snap-converted") == 1      # only the figure that has one


def test_a_snapshot_saved_before_conversion_existed_still_opens(page, tmp_path):  # noqa: F811
    snapshot = build_snapshot(final_state())
    for kept in snapshot["figures"]:
        del kept["converted"]

    app = with_snapshot(page, tmp_path, snapshot=snapshot)

    assert not app.exception
    assert "1 billion EUR" in snapshot_html(app)


def test_open_report_and_ask_lead_out_of_the_snapshot(page, tmp_path):  # noqa: F811
    app = with_snapshot(page, tmp_path)

    button(app, "snapshot_report").click().run()
    assert button(app, "view_report").proto.type == "secondary"

    button(app, "view_snapshot").click().run()
    button(app, "snapshot_ask").click().run()
    assert button(app, "view_ask").proto.type == "secondary"
    assert len(app.chat_input) == 1


def test_after_a_follow_up_the_conversation_opens_on_ask(page, tmp_path):  # noqa: F811
    app = with_snapshot(page, tmp_path, replies=[AIMessage("A follow-up answer.")])
    button(app, "view_ask").click().run()

    app.chat_input[0].set_value("And the prices?").run()
    again = AppTest.from_file(APP, default_timeout=30)
    again.query_params["c"] = "snap"
    again.run()

    assert button(again, "view_ask").proto.type == "secondary"
    assert view_links(again) == ["Snapshot", "Ask", "Report"]


def test_a_report_made_before_snapshots_existed_has_no_snapshot_link(page, tmp_path):  # noqa: F811
    from tests.test_views import with_a_report

    assert view_links(with_a_report(page, tmp_path)) == ["Ask", "Report"]
