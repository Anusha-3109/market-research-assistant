"""Tests for the tabs of the Snapshot view: Overview, Competitors, Pricing,
Trends and SWOT, under a line that says how many sources the report used.

Every tab shows figures that were kept with the report. A tab with nothing
to show says so; nothing is invented to fill it.
"""

from agent.report.snapshot import build_snapshot
from tests.test_app import page  # noqa: F401  (page is a fixture)
from tests.test_snapshot import final_state, snapshot_html, with_snapshot

CITED = ("# Market research report: oat milk in Germany\n\n## 1. Market overview\n\n"
         "- A fact ([A](https://a.example/m)).\n- Another ([B](https://b.example/g)).\n"
         "- Again ([A](https://a.example/m)).")


def tab(app, label):
    return next(tab for tab in app.tabs if tab.label == label)


def shown_in(app, label) -> str:
    return "\n".join(element.proto.body for element in tab(app, label).get("html"))


# --- what is kept ----------------------------------------------------------------------------------

def test_the_snapshot_keeps_all_four_parts_of_the_swot():
    snapshot = build_snapshot(final_state())

    assert snapshot["strengths"] == ["s"]
    assert snapshot["weaknesses"] == ["w"]
    assert snapshot["threats"] == ["t"]


def test_a_report_without_a_swot_keeps_empty_lists():
    state = final_state()
    state["swot"] = None

    snapshot = build_snapshot(state)

    assert (snapshot["strengths"], snapshot["weaknesses"]) == ([], [])


# --- on the page ---------------------------------------------------------------------------------

def test_the_snapshot_has_five_tabs_in_a_fixed_order(page, tmp_path):  # noqa: F811
    app = with_snapshot(page, tmp_path)

    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Overview", "Competitors", "Pricing", "Trends", "SWOT"]


def test_a_line_says_how_many_sources_the_report_used(page, tmp_path):  # noqa: F811
    shown = snapshot_html(with_snapshot(page, tmp_path, report=CITED))

    assert "Snapshot generated from 2 sources" in shown        # a page cited twice counts once


def test_a_report_that_cites_nothing_has_no_such_line(page, tmp_path):  # noqa: F811
    assert "Snapshot generated from" not in snapshot_html(with_snapshot(page, tmp_path))


def test_the_overview_holds_the_figures_and_nothing_else(page, tmp_path):  # noqa: F811
    overview = shown_in(with_snapshot(page, tmp_path), "Overview")

    assert "1 billion EUR" in overview and "Competitors confirmed" in overview
    assert "Oatly" not in overview and "Hafermilch" not in overview


def test_the_competitors_tab_says_who_they_are_and_how_large(page, tmp_path):  # noqa: F811
    competitors = shown_in(with_snapshot(page, tmp_path), "Competitors")

    assert "Oatly" in competitors and "Oat drinks in six varieties" in competitors
    assert "Revenue: 783 million USD; Employees: 1,500" in competitors
    assert "2.49 EUR" not in competitors                       # prices have their own tab


def test_the_pricing_tab_has_one_price_each_and_says_what_was_not_found(page, tmp_path):  # noqa: F811
    pricing = shown_in(with_snapshot(page, tmp_path), "Pricing")

    assert "<td>Oatly</td><td>2.49 EUR (Barista 1 l)</td>" in pricing
    assert "<td>Alpro</td><td>not found" in pricing
    assert "The shop page shows no prices." in pricing                     # and why
    assert "Revenue" not in pricing


def test_the_trends_tab_holds_the_chart(page, tmp_path):  # noqa: F811
    trends = shown_in(with_snapshot(page, tmp_path), "Trends")

    assert "Hafermilch" in trends and "rising (+32%)" in trends
    assert trends.count('class="gw-snap-bar') == 13            # the row of bars and its 12 bars


def test_the_swot_tab_has_four_named_boxes(page, tmp_path):  # noqa: F811
    swot = shown_in(with_snapshot(page, tmp_path), "SWOT")

    heads = [part.split("<")[0] for part in swot.split('class="gw-snap-head">')[1:]]
    assert heads == ["Strengths", "Weaknesses", "Opportunities", "Risks"]
    assert "<li>s</li>" in swot and "<li>w</li>" in swot and "<li>t</li>" in swot
    assert "<li>Barista editions grow fastest</li>" in swot


def test_an_older_snapshot_shows_only_the_parts_of_the_swot_it_kept(page, tmp_path):  # noqa: F811
    snapshot = build_snapshot(final_state())
    for part in ("strengths", "weaknesses", "threats"):
        del snapshot[part]

    app = with_snapshot(page, tmp_path, snapshot=snapshot)

    assert not app.exception
    swot = shown_in(app, "SWOT")
    assert "Opportunities" in swot and "Strengths" not in swot and "Risks" not in swot


def test_a_tab_with_nothing_to_show_says_so(page, tmp_path):  # noqa: F811
    snapshot = build_snapshot(final_state())
    snapshot.update(competitors=[], trend=None, opportunities=[], strengths=[], weaknesses=[],
                    threats=[])

    app = with_snapshot(page, tmp_path, snapshot=snapshot)

    assert "No competitors were confirmed for this report." in shown_in(app, "Competitors")
    assert "No competitors were confirmed, so there are no prices." in shown_in(app, "Pricing")
    assert "No demand trend was measured for this report." in shown_in(app, "Trends")
    assert "The report has no SWOT section." in shown_in(app, "SWOT")


def test_a_snapshot_saved_before_the_reason_was_kept_shows_not_found_alone(page, tmp_path):  # noqa: F811
    old = build_snapshot(final_state())
    for row in old["competitors"]:
        del row["price_note"]

    pricing = shown_in(with_snapshot(page, tmp_path, snapshot=old), "Pricing")

    assert "<td>Alpro</td><td>not found</td>" in pricing


def test_the_reason_is_in_german_too(page, tmp_path):  # noqa: F811
    from tests.test_language import switch as language_switch
    snapshot = build_snapshot(final_state())
    snapshot["competitors"][1]["price_note"] = "no prices are shown on the pages that were read"
    app = with_snapshot(page, tmp_path, snapshot=snapshot)

    language_switch(app).set_value("de").run()

    assert "auf den gelesenen Seiten werden keine Preise gezeigt" in shown_in(app, "Preise")