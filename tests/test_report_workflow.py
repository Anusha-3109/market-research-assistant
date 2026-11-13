"""Tests for the report workflow, steps 1 to 3.

The model and the search are replaced with fakes, so the whole graph runs
without the internet and without cost. The fake model returns whatever the
test tells it to; the tests then check what the CODE does with that answer.
"""

from agent.report import steps
from agent.report.deps import Deps
from agent.report.graph import build_report_graph
from agent.report.state import (
    Candidate,
    CandidateList,
    MarketFigureList,
    NewsList,
    PriceList,
    ResearchBrief,
    TermCheck,
    Verdict,
)

BRIEF = ResearchBrief(
    local_language="German", category_terms=["Kochbox"],
    competitor_query="Kochbox Anbieter Deutschland",
    market_query="Kochbox Markt Deutschland", price_word="Preise",
    trend_terms=["Kochbox", "Fertiggerichte", "Essenslieferung"])


def page(url: str, title: str = "", content: str = "") -> dict:
    return {"title": title, "url": url, "content": content}


def make_deps(candidates: list[Candidate], verdicts: dict[str, Verdict],
              pages: dict[str, list[dict]] | None = None, calls: list | None = None) -> Deps:
    """Build fake dependencies.

    candidates: what the fake model lists in step 2.
    verdicts:   the fake model's verdict for each company name in step 3.
    pages:      search results by query; any other query returns DEFAULT_PAGES.
    """
    pages = pages or {}

    def ask(schema, instructions, material):
        if calls is not None:
            calls.append(schema.__name__)
        if schema is ResearchBrief:
            return BRIEF
        if schema is CandidateList:
            return CandidateList(candidates=candidates)
        # The later research steps get empty answers: these tests are about
        # choosing competitors. test_report_research.py covers the rest.
        if schema is PriceList:
            return PriceList(prices=[])
        if schema is MarketFigureList:
            return MarketFigureList(figures=[])
        if schema is TermCheck:
            return TermCheck(specific=True, reason="test")
        if schema is NewsList:
            return NewsList(items=[])
        for name, verdict in verdicts.items():
            if f"'{name}'" in instructions:
                return verdict
        raise AssertionError(f"no fake verdict for: {instructions}")

    def search(query):
        return pages.get(query, DEFAULT_PAGES)

    return Deps(ask=ask, search=search, news=lambda query: [],
                read_page=lambda url: None, financials=lambda name: None,
                trend=lambda term, country: None)


DEFAULT_PAGES = [
    page("https://list.example/top", "Top meal kits", "HelloFresh leads the market and keeps growing."),
    page("https://www.hellofresh.de", "HelloFresh Kochbox", "HelloFresh delivers in Germany"),
    page("https://marleyspoon.de", "Marley Spoon", "Kochbox from Marley Spoon"),
    page("https://www.cookunity.com", "CookUnity", "Chef meals in the US"),
]


def yes(shop: str, evidence: str | None = None) -> Verdict:
    return Verdict(sells_this_product=True, operates_in_country=True, shop_url=shop,
                   evidence_url=evidence or shop, reason="sells meal kits in Germany")


def run(deps: Deps, country: str = "Germany") -> dict:
    return build_report_graph(deps).invoke({"product": "meal kits", "country": country})


# --- helpers ------------------------------------------------------------------------

def test_name_key_ignores_case_accents_and_punctuation():
    assert steps.name_key("Löwenanteil GmbH") == steps.name_key("lowenanteil gmbh")
    assert steps.name_key("Marley-Spoon") == "marleyspoon"


def test_is_own_site_recognises_the_brand_in_the_address():
    assert steps.is_own_site("HelloFresh", "https://www.hellofresh.de/plans")
    assert steps.is_own_site("Marley Spoon", "https://marleyspoon.de")
    assert steps.is_own_site("Löwenanteil", "https://www.loewenanteil.com")


def test_is_own_site_rejects_a_page_about_the_company_on_another_site():
    assert not steps.is_own_site("HelloFresh", "https://www.stripes.com/hellofresh-review")
    assert not steps.is_own_site("HelloFresh", "https://blog.example/best-meal-kits")


def test_known_url_ignores_a_trailing_slash_but_rejects_other_addresses():
    results = [page("https://www.hellofresh.de/")]

    assert steps.known_url("https://www.hellofresh.de", results)
    assert not steps.known_url("https://www.hellofresh.de/invented", results)
    assert not steps.known_url("", results)


def test_count_mentions_counts_results_that_name_the_company():
    assert steps.count_mentions("HelloFresh", DEFAULT_PAGES) == 2
    assert steps.count_mentions("CookUnity", DEFAULT_PAGES) == 1
    assert steps.count_mentions("Unknown Co", DEFAULT_PAGES) == 0


# --- the whole graph ----------------------------------------------------------------

def test_a_verified_company_becomes_a_competitor_with_its_shop_address():
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top")],
        {"HelloFresh": yes("https://www.hellofresh.de")})

    result = run(deps)

    assert [c.name for c in result["competitors"]] == ["HelloFresh"]
    assert result["competitors"][0].shop_url == "https://www.hellofresh.de"
    assert result["country"] == "Germany"


def test_the_country_name_is_normalised(monkeypatch):
    deps = make_deps([], {})

    assert run(deps, country="germany")["country"] == "Germany"
    assert run(deps, country="UK")["country"] == "United Kingdom"


def test_a_company_from_another_country_is_dropped_with_the_reason():
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top"),
         Candidate(name="CookUnity", mentioned_at="https://www.cookunity.com")],
        {"HelloFresh": yes("https://www.hellofresh.de"),
         "CookUnity": Verdict(sells_this_product=True, operates_in_country=False,
                              shop_url="https://www.cookunity.com",
                              evidence_url="https://www.cookunity.com",
                              reason="only delivers in the US")})

    result = run(deps)

    assert [c.name for c in result["competitors"]] == ["HelloFresh"]
    assert [(r.name, r.reason) for r in result["rejected"]] == [
        ("CookUnity", "not active in Germany: only delivers in the US")]


def test_a_company_selling_a_different_product_is_dropped():
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top")],
        {"HelloFresh": Verdict(sells_this_product=False, operates_in_country=True,
                               shop_url="", evidence_url="https://list.example/top",
                               reason="grocery delivery")})

    result = run(deps)

    assert result["competitors"] == []
    assert result["rejected"][0].reason == "different product: grocery delivery"


def test_a_candidate_whose_source_page_was_invented_is_ignored():
    deps = make_deps(
        [Candidate(name="Ghost Foods", mentioned_at="https://made-up.example/ghost")],
        {})

    result = run(deps)

    assert result["candidates"] == []
    assert result["competitors"] == []


def test_the_same_company_listed_twice_is_checked_once():
    calls = []
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top"),
         Candidate(name="hellofresh", mentioned_at="https://www.hellofresh.de")],
        {"HelloFresh": yes("https://www.hellofresh.de")}, calls=calls)

    result = run(deps)

    assert len(result["candidates"]) == 1
    assert calls.count("Verdict") == 1


def test_a_shop_address_on_someone_elses_site_is_not_accepted_as_the_shop():
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top")],
        {"HelloFresh": yes(shop="https://list.example/top")})

    competitor = run(deps)["competitors"][0]

    assert competitor.shop_url == ""                              # not the company's site
    assert competitor.evidence_url == "https://list.example/top"   # still valid evidence


def test_an_invented_shop_address_is_not_accepted():
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top")],
        {"HelloFresh": yes(shop="https://www.hellofresh.de/invented-page",
                           evidence="https://list.example/top")})

    assert run(deps)["competitors"][0].shop_url == ""


def test_a_positive_verdict_without_any_real_evidence_page_is_dropped():
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top")],
        {"HelloFresh": yes(shop="https://invented.example", evidence="https://invented.example")})

    result = run(deps)

    assert result["competitors"] == []
    assert "no page among the results" in result["rejected"][0].reason


def test_competitors_are_ranked_by_how_often_the_results_mention_them():
    deps = make_deps(
        # The model lists Marley Spoon first, but the results mention HelloFresh more.
        [Candidate(name="Marley Spoon", mentioned_at="https://marleyspoon.de"),
         Candidate(name="HelloFresh", mentioned_at="https://list.example/top")],
        {"Marley Spoon": yes("https://marleyspoon.de"),
         "HelloFresh": yes("https://www.hellofresh.de")})

    assert [c.name for c in run(deps)["competitors"]] == ["HelloFresh", "Marley Spoon"]


def test_only_the_top_competitors_are_kept(monkeypatch):
    monkeypatch.setattr(steps, "REPORT_MAX_COMPETITORS", 1)
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top"),
         Candidate(name="Marley Spoon", mentioned_at="https://marleyspoon.de")],
        {"Marley Spoon": yes("https://marleyspoon.de"),
         "HelloFresh": yes("https://www.hellofresh.de")})

    result = run(deps)

    assert [c.name for c in result["competitors"]] == ["HelloFresh"]
    assert any("left out" in line and "Marley Spoon" in line for line in result["log"])


def test_no_search_results_gives_an_empty_report_instead_of_an_error():
    calls = []
    deps = make_deps([], {}, calls=calls)
    deps.search = lambda query: []

    result = run(deps)

    assert result["competitors"] == []
    assert "CandidateList" not in calls    # the model is not asked about nothing


def test_a_candidate_with_no_search_results_is_dropped():
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top")],
        {}, pages={"HelloFresh Germany": [], "HelloFresh Kochbox": []})

    result = run(deps)

    assert result["rejected"][0].reason == "no search results"


def test_each_step_adds_a_progress_line():
    deps = make_deps(
        [Candidate(name="HelloFresh", mentioned_at="https://list.example/top")],
        {"HelloFresh": yes("https://www.hellofresh.de")})

    log = run(deps)["log"]

    assert log[0] == "Search terms (German): Kochbox"
    assert log[1] == "Candidates found: HelloFresh"
    assert log[2] == "Confirmed competitors: HelloFresh"
