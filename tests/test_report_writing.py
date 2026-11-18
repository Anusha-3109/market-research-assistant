"""Tests for steps 8 and 9 of the report workflow: building the report text,
the SWOT retry, and the tool the chat agent calls. No internet."""

from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import tools
from agent.report import render, writing
from agent.report.deps import Deps
from agent.report.state import (
    Competitor,
    CompetitorProfile,
    MarketFigure,
    NewsItem,
    PricePoint,
    Swot,
    TrendResult,
)
from agent.report.tool import create_market_report, run_report
from agent.report_check import check_report

TODAY = date.today().isoformat()

HELLOFRESH_FIGURES = (
    "Source used: Yahoo Finance\nCompany: HelloFresh SE (ticker HFG.DE)\n"
    "Revenue (last 12 months): 6.2 billion EUR\nEmployees: 11447\n"
    "Source: https://finance.yahoo.com/quote/HFG.DE")

GOOD_SWOT = Swot(strengths=["Fresh brand", "Low prices"],
                 weaknesses=["No customers yet", "No logistics"],
                 opportunities=["Growing market", "Vegan demand"],
                 threats=["HelloFresh's scale", "Price pressure"])

# What the report's details say about model calls when the stand-in workflow
# made none.
NOTHING_USED = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                "cost": 0.0, "priced_calls": 0}



def competitor(name: str, shop: str = "", offer: str = "Meal kits") -> Competitor:
    return Competitor(name=name, shop_url=shop, evidence_url=f"https://list.example/{name}",
                      reason="sells meals in Germany", offer=offer)


def profile(name: str, shop: str = "", figures: str = "", figures_source: str = "",
            prices: list | None = None, price_source: str = "",
            price_note: str = "") -> CompetitorProfile:
    return CompetitorProfile(name=name, shop_url=shop, figures=figures,
                             figures_source=figures_source, prices=prices or [],
                             price_source=price_source, price_note=price_note)


def full_state() -> dict:
    """A workflow state with every kind of fact in it."""
    return {
        "product": "meal kits", "country": "Germany", "idea": "",
        "competitors": [competitor("HelloFresh", "https://www.hellofresh.de"),
                        competitor("Prepmymeal", "https://prepmymeal.com", "Frozen meals")],
        "profiles": [
            # Deliberately in the wrong order: the report must follow "competitors".
            profile("Prepmymeal", "https://prepmymeal.com",
                    prices=[PricePoint(product="6-meal box", price="€9.99 per portion")],
                    price_source="https://prepmymeal.com/boxes"),
            profile("HelloFresh", "https://www.hellofresh.de", figures=HELLOFRESH_FIGURES,
                    figures_source="https://finance.yahoo.com/quote/HFG.DE",
                    price_note="no prices are shown on the pages that were read"),
        ],
        "market_figures": [
            MarketFigure(statement="market size", value="EUR 1.2 billion", area="Germany",
                         scope="country", year="2025", source_url="https://de.example/report"),
            MarketFigure(statement="market size", value="USD 9.5 billion", area="Europe",
                         scope="wider", year="2024", source_url="https://eu.example/report"),
        ],
        "news": [NewsItem(summary="HelloFresh opens a plant.", date="2026-11-01",
                          source_url="https://news.example/a")],
        "trend": TrendResult(
            term="Kochbox", reliable=True,
            summary="Google search interest for 'Kochbox' in Germany\n"
                    "Direction: falling (-25% from the first to the last quarter of the period)\n"
                    "Source: https://trends.google.com/x"),
        "swot": GOOD_SWOT,
    }


# --- the report text ------------------------------------------------------------------

def test_a_report_built_from_facts_passes_the_report_check():
    assert check_report(render.render_report(full_state())) == []


def test_competitors_appear_in_ranked_order_not_in_the_order_they_finished():
    report = render.render_report(full_state())

    assert report.index("| HelloFresh |") < report.index("| Prepmymeal |")


def test_a_price_row_links_to_the_page_the_price_was_read_from():
    report = render.render_report(full_state())

    assert (f"| Prepmymeal | 6-meal box | €9.99 per portion "
            f"| [company website](https://prepmymeal.com/boxes) | {TODAY} |") in report


def test_a_competitor_without_prices_still_gets_a_row_with_the_reason():
    report = render.render_report(full_state())

    assert ("| HelloFresh | not found | not found (no prices are shown on the pages "
            "that were read) | [checked](https://www.hellofresh.de) |") in report


def test_company_figures_are_shown_with_their_source():
    report = render.render_report(full_state())

    assert "Revenue (last 12 months): 6.2 billion EUR; Employees: 11447" in report
    assert "[figures](https://finance.yahoo.com/quote/HFG.DE)" in report


def test_figures_for_a_different_company_with_a_similar_name_are_not_used():
    # A lookup for the brand "Bulk" that matched an unrelated listed company.
    wrong = profile("Bulk", figures="Source used: Yahoo Finance\n"
                                    "Company: Dry Shipping Carriers Inc (ticker DSX)\n"
                                    "Revenue (last 12 months): 250.0 million USD",
                    figures_source="https://finance.yahoo.com/quote/DSX")

    assert render.trusted_figures(wrong) == []


def test_figures_for_a_company_that_merely_contains_the_brand_name_are_not_used():
    wrong = profile("Factor", figures="Source used: Yahoo Finance\n"
                                      "Company: The Cheesecake Factory Incorporated (ticker CAKE)\n"
                                      "Revenue (last 12 months): 4.0 billion USD",
                    figures_source="https://finance.yahoo.com/quote/CAKE")

    assert render.trusted_figures(wrong) == []


def test_a_figure_for_a_wider_area_says_so():
    section = render.market_section(full_state())

    assert "USD 9.5 billion (Europe, 2024). Note: this covers Europe, not Germany alone." in section
    assert "EUR 1.2 billion (Germany, 2025). [source]" in section


def test_the_demand_trend_is_reported_as_interest_not_sales():
    section = render.trends_section(full_state())

    assert ("Search interest for 'Kochbox' in Germany over the last 12 months: falling "
            "(-25% from the first to the last quarter of the period). This measures "
            "searches, not sales. [source](https://trends.google.com/x)") in section


def test_an_unreliable_trend_carries_a_warning():
    state = full_state()
    state["trend"] = state["trend"].model_copy(update={"reliable": False})

    assert "Reliability is low" in render.trends_section(state)


def test_a_missing_trend_is_stated_plainly():
    state = full_state()
    state["trend"] = None

    assert "No reliable demand trend was found" in render.trends_section(state)


def test_the_swot_says_who_it_is_written_for():
    assert "a new entrant in this market" in render.swot_section(GOOD_SWOT, idea="")
    assert "the business idea described by the user" in render.swot_section(
        GOOD_SWOT, idea="vegan protein bowls")


def test_references_list_every_link_once_in_order_of_appearance():
    references = render.references_section(
        "a [source](https://one.example) b [source](https://two.example)",
        "c [source](https://one.example)")

    assert references == "1. https://one.example\n2. https://two.example\n"


def test_a_column_separator_inside_a_fact_cannot_break_the_table():
    assert render.cell("Box A | Box B\nnew line") == "Box A / Box B new line"


def test_a_long_description_is_shortened():
    assert render.shorten("one two three four five", max_words=3) == "one two three…"
    assert render.shorten("short text") == "short text"


def test_a_report_with_no_facts_at_all_still_renders_and_says_what_is_missing():
    report = render.render_report({"product": "meal kits", "country": "Germany"})

    assert "No market figures with a checkable source were found." in report
    assert "No direct competitors could be confirmed" in report
    assert "The analysis could not be produced." in report


# --- the SWOT step and its retry ---------------------------------------------------------

def writing_steps(replies: list) -> dict:
    """Writing steps whose fake model gives the listed replies in turn. A
    reply that is an exception is raised, like a failed model call."""
    queue = iter(replies)

    def ask(schema, instructions, material):
        reply = next(queue)
        if isinstance(reply, Exception):
            raise reply
        return reply

    return writing.make_writing_steps(Deps(
        ask=ask, search=None, news=None, read_page=None, financials=None, trend=None))


INCOMPLETE = Swot(strengths=["Only one"], weaknesses=[], opportunities=[], threats=[])


def test_a_swot_needs_at_least_two_points_in_each_list():
    assert writing.swot_is_complete(GOOD_SWOT)
    assert not writing.swot_is_complete(INCOMPLETE)
    assert not writing.swot_is_complete(None)


def test_an_incomplete_swot_is_sent_back_once():
    assert writing.after_swot({"swot": INCOMPLETE, "swot_attempts": 1}) == "write_swot"


def test_after_the_second_attempt_the_workflow_moves_on_regardless():
    assert writing.after_swot({"swot": INCOMPLETE, "swot_attempts": 2}) == "assemble_report"


def test_a_complete_swot_moves_straight_on():
    assert writing.after_swot({"swot": GOOD_SWOT, "swot_attempts": 1}) == "assemble_report"


def test_a_failed_model_call_counts_as_an_incomplete_swot():
    steps = writing_steps([TimeoutError("model timed out")])

    result = steps["write_swot"](full_state())

    assert result["swot"] is None
    assert result["swot_attempts"] == 1


def test_the_swot_step_gives_the_model_the_facts_and_the_users_idea():
    seen = {}

    def ask(schema, instructions, material):
        seen["material"] = material
        return GOOD_SWOT

    steps = writing.make_writing_steps(Deps(
        ask=ask, search=None, news=None, read_page=None, financials=None, trend=None))

    steps["write_swot"]({**full_state(), "idea": "vegan protein bowls"})

    assert "vegan protein bowls" in seen["material"]
    assert "EUR 1.2 billion" in seen["material"]
    assert "€9.99 per portion" in seen["material"]


def test_an_incomplete_swot_is_left_out_of_the_final_report():
    steps = writing_steps([])

    result = steps["assemble_report"]({**full_state(), "swot": INCOMPLETE})

    assert "The analysis could not be produced." in result["report"]
    assert "Only one" not in result["report"]


def test_the_assembled_report_comes_with_its_check_result():
    result = writing_steps([])["assemble_report"](full_state())

    assert result["problems"] == []
    assert result["log"] == ["Report check: passed"]


# --- the tool the chat agent calls -------------------------------------------------------------

class FakeGraph:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.request = result, error, None

    def stream(self, request, stream_mode=None):
        """Like the real graph: step updates first, then the final state."""
        self.request = request
        if self.error:
            raise self.error
        yield "updates", {"some_step": {"log": ["Step one done"]}}
        yield "updates", {"__interrupt__": ()}      # not a dict of fields
        yield "values", self.result


def test_the_tool_returns_the_report_and_keeps_the_check_result_aside():
    graph = FakeGraph({"report": "# Market research report: x", "problems": [],
                       "log": ["Report check: passed"]})

    text, details = run_report("meal kits", "Germany", "vegan bowls", graph=graph)

    assert text == "# Market research report: x"
    # The key figures travel with it too; they have their own tests in
    # test_snapshot.py.
    snapshot = details.pop("snapshot")
    assert snapshot["figures"] == [] and snapshot["competitors"] == []
    assert details == {"problems": [], "log": ["Report check: passed"],
                       "titles": {}, "official": [], "usage": NOTHING_USED}
    assert graph.request == {"product": "meal kits", "country": "Germany",
                             "idea": "vegan bowls", "style": "Balanced"}


def test_the_tool_passes_on_page_titles_and_the_competitors_own_sites():
    state = full_state()
    state.update(report="# Market research report: x", problems=[], log=[],
                 titles={"https://prepmymeal.com/boxes": "Prepmymeal: prices"})

    _, details = run_report("meal kits", "Germany", "", graph=FakeGraph(state))

    assert details["titles"] == {"https://prepmymeal.com/boxes": "Prepmymeal: prices"}
    # The shop addresses and the page the prices were read from.
    assert details["official"] == ["hellofresh.de", "prepmymeal.com"]


def test_the_tool_asks_for_a_real_country_without_running_the_workflow():
    graph = FakeGraph({})

    text, details = run_report("meal kits", "Europe", "", graph=graph)

    assert "could not recognise 'Europe' as a country" in text
    assert graph.request is None


def test_the_tool_asks_for_a_product_when_it_is_empty():
    text, _ = run_report("  ", "Germany", "", graph=FakeGraph({}))

    assert "which product or industry" in text


def test_a_failure_inside_the_workflow_becomes_a_readable_message():
    text, details = run_report("meal kits", "Germany", "",
                               graph=FakeGraph(error=ConnectionError("no internet")))

    assert text.startswith("The report could not be produced")
    assert "no internet" in text
    assert details == {"usage": NOTHING_USED}


def test_progress_lines_are_passed_on_as_each_step_finishes():
    graph = FakeGraph({"report": "# Market research report: x", "problems": [], "log": []})
    seen = []

    run_report("meal kits", "Germany", "", graph=graph, on_progress=seen.append)

    assert seen == ["Step one done"]


def test_a_run_that_produces_no_report_gives_a_readable_message():
    text, details = run_report("meal kits", "Germany", "", graph=FakeGraph({}))

    assert text.startswith("The report could not be produced")
    assert details == {"usage": NOTHING_USED}


def test_the_report_tool_hands_its_result_straight_to_the_user():
    # return_direct means the chat model does not retype the report.
    assert create_market_report.return_direct is True
    assert create_market_report.name == "create_market_report"


# --- saving a report made by the workflow ---------------------------------------------------

def test_save_report_finds_a_report_returned_by_the_workflow_tool():
    messages = [
        HumanMessage("Give me a report"),
        ToolMessage(content="# Market research report: meal kits in Germany\nPrice: €5",
                    tool_call_id="1", name="create_market_report"),
        HumanMessage("Save this report."),
    ]

    assert tools.find_last_report(messages) == (
        "# Market research report: meal kits in Germany\nPrice: €5")


def test_save_report_takes_the_newest_report_of_either_kind():
    messages = [
        ToolMessage(content="# Market research report: old", tool_call_id="1",
                    name="create_market_report"),
        AIMessage("# Market research report: newer one"),
    ]

    assert tools.find_last_report(messages) == "# Market research report: newer one"
