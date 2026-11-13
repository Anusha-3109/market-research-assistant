"""Tests for steps 4 to 7 of the report workflow: figures, prices, market
figures, news and the demand trend.

Each step is called directly with fake dependencies, so the tests show what
the CODE accepts and rejects from the model's answers.
"""

from agent.report import research
from agent.report.deps import Deps
from agent.report.state import (
    Competitor,
    MarketFigure,
    MarketFigureList,
    NewsItem,
    NewsList,
    PriceList,
    PricePoint,
    ResearchBrief,
    TermCheck,
)
from agent.trends import TrendSeries

BRIEF = ResearchBrief(
    local_language="German", category_terms=["Kochbox"],
    competitor_query="Kochbox Anbieter Deutschland",
    market_query="Kochbox Markt Deutschland", price_word="Preise",
    trend_terms=["Kochbox", "Fertiggerichte", "Essenslieferung"])

SHOP = Competitor(name="HelloFresh", shop_url="https://www.hellofresh.de",
                  evidence_url="https://www.hellofresh.de", reason="sells meal kits")
TASK = {"competitor": SHOP, "country": "Germany", "price_word": "Preise"}


def page(url: str, title: str = "", content: str = "") -> dict:
    return {"title": title, "url": url, "content": content}


def make_steps(answers: dict | None = None, search=None, news=None,
               pages: dict | None = None, financials=None, trend=None,
               opened: list | None = None) -> dict:
    """Build the research steps around fakes.

    answers: the fake model's reply for each schema.
    pages:   the text of each web page, by address.
    opened:  if given, every address that is opened is added to it.
    """
    answers, pages = answers or {}, pages or {}

    def read_page(url):
        if opened is not None:
            opened.append(url)
        return pages.get(url)

    deps = Deps(
        ask=lambda schema, instructions, material: answers[schema],
        search=search or (lambda query: []),
        news=news or (lambda query: []),
        read_page=read_page,
        financials=financials or (lambda name: None),
        trend=trend or (lambda term, country: None),
    )
    return research.make_research_steps(deps)


def prices(*items: tuple[str, str]) -> PriceList:
    return PriceList(prices=[PricePoint(product=p, price=v) for p, v in items])


# --- checking that a figure was copied, not invented ------------------------------------

def test_a_price_is_accepted_when_its_number_is_on_the_page():
    assert research.is_quoted_from("€39.99 per week", "Classic box 39.99 € weekly")


def test_a_comma_and_a_point_are_the_same_price():
    assert research.is_quoted_from("€7.99", "nur 7,99 € pro Gericht")
    assert research.is_quoted_from("7,99 €", "only 7.99 per meal")


def test_a_price_that_is_not_on_the_page_is_rejected():
    assert not research.is_quoted_from("€29.99", "Classic box 39.99 € weekly")


def test_a_number_hidden_inside_a_longer_number_does_not_count():
    # "5" must not be accepted just because the text contains "2025".
    assert not research.is_quoted_from("EUR 5 billion", "EUR 1.2 billion in 2025")


def test_a_shop_word_in_the_domain_name_is_not_a_price_page_hint():
    ranked = research.rank_price_pages(
        ["https://myshop.example/about", "https://myshop.example/pricing"])

    assert ranked[0] == "https://myshop.example/pricing"


def test_a_price_without_any_number_is_rejected():
    assert not research.is_quoted_from("on request", "prices on request")


def test_pages_that_look_like_price_pages_are_tried_first():
    ranked = research.rank_price_pages([
        "https://shop.example/about", "https://shop.example/preise/",
        "https://shop.example/about", "https://shop.example"])

    assert ranked == ["https://shop.example/preise", "https://shop.example/about",
                      "https://shop.example"]


def test_source_link_is_read_from_the_financials_text():
    text = "Source used: Yahoo Finance\nRevenue: 6.2 billion EUR\nSource: https://finance.yahoo.com/quote/HFG.DE\nRetrieved: today"

    assert research.source_link(text) == "https://finance.yahoo.com/quote/HFG.DE"
    assert research.source_link("") == ""


# --- steps 4 and 5: one competitor ---------------------------------------------------------

def test_prices_are_read_from_the_companys_own_page_and_sourced_to_it():
    steps = make_steps(
        answers={PriceList: prices(("Classic box", "€39.99 per week"))},
        search=lambda query: [page("https://www.hellofresh.de/preise")],
        pages={"https://www.hellofresh.de/preise": "Classic box 39,99 € pro Woche"})

    profile = steps["research_competitor"](TASK)["profiles"][0]

    assert profile.prices == [PricePoint(product="Classic box", price="€39.99 per week")]
    assert profile.price_source == "https://www.hellofresh.de/preise"
    assert profile.price_note == ""


def test_third_party_pages_are_never_opened_for_prices():
    opened = []
    steps = make_steps(
        answers={PriceList: prices()},
        search=lambda query: [page("https://www.stripes.com/hellofresh-review-2021"),
                              page("https://blog.example/hellofresh-preise")],
        pages={}, opened=opened)

    steps["research_competitor"](TASK)

    assert opened == ["https://www.hellofresh.de"]     # only the company's own site


def test_an_invented_price_is_dropped_and_real_ones_are_kept():
    steps = make_steps(
        answers={PriceList: prices(("Classic box", "€39.99"), ("Family box", "€19.99"))},
        search=lambda query: [],
        pages={"https://www.hellofresh.de": "Classic box 39,99 €"})

    profile = steps["research_competitor"](TASK)["profiles"][0]

    assert [p.product for p in profile.prices] == ["Classic box"]


def test_the_next_page_is_tried_when_the_first_shows_no_prices():
    opened = []
    # The fake model finds no prices on the first page and one on the second.
    replies = iter([prices(), prices(("Classic box", "€39.99"))])
    site = {"https://www.hellofresh.de/preise": "Welcome to HelloFresh",
            "https://www.hellofresh.de": "Classic box 39,99 €"}

    def read_page(url):
        opened.append(url)
        return site.get(url)

    steps = research.make_research_steps(Deps(
        ask=lambda schema, instructions, material: next(replies),
        search=lambda query: [page("https://www.hellofresh.de/preise")],
        news=lambda query: [], read_page=read_page,
        financials=lambda name: None, trend=lambda term, country: None))

    profile = steps["research_competitor"](TASK)["profiles"][0]

    assert opened == ["https://www.hellofresh.de/preise", "https://www.hellofresh.de"]
    assert profile.price_source == "https://www.hellofresh.de"


def test_no_prices_on_the_site_is_reported_as_not_found_with_the_reason():
    steps = make_steps(
        answers={PriceList: prices()},
        pages={"https://www.hellofresh.de": "Welcome to HelloFresh"})

    profile = steps["research_competitor"](TASK)["profiles"][0]

    assert profile.prices == []
    assert profile.price_source == ""
    assert profile.price_note == "no prices are shown on the pages that were read"


def test_a_site_that_cannot_be_read_is_reported_as_such():
    steps = make_steps(pages={})

    profile = steps["research_competitor"](TASK)["profiles"][0]

    assert profile.price_note == "the company's website could not be read"


def test_a_competitor_without_a_known_website_gets_a_clear_note():
    no_site = Competitor(name="Tiny Meals", shop_url="", evidence_url="https://list.example",
                         reason="sells meals")
    steps = make_steps()

    profile = steps["research_competitor"]({**TASK, "competitor": no_site})["profiles"][0]

    assert profile.price_note == "the company's own website was not found"


def test_figures_and_their_source_link_are_stored():
    figures = "Source used: Yahoo Finance\nRevenue: 6.2 billion EUR\nSource: https://finance.yahoo.com/quote/HFG.DE"
    steps = make_steps(financials=lambda name: figures)

    profile = steps["research_competitor"](TASK)["profiles"][0]

    assert profile.figures == figures
    assert profile.figures_source == "https://finance.yahoo.com/quote/HFG.DE"


# --- step 6: the market ----------------------------------------------------------------------

MARKET_PAGES = [
    page("https://de.example/report", "German meal kit market",
         "The German market reached EUR 1.2 billion in 2025."),
    page("https://eu.example/report", "Europe meal kits",
         "Europe was worth USD 9.5 billion in 2024."),
]
STATE = {"product": "meal kits", "country": "Germany", "brief": BRIEF}


def figure(value: str, scope: str, url: str, area: str = "Germany") -> MarketFigure:
    return MarketFigure(statement="market size", value=value, area=area, scope=scope,
                        year="2025", source_url=url)


def market_step(*figures: MarketFigure) -> dict:
    steps = make_steps(answers={MarketFigureList: MarketFigureList(figures=list(figures))},
                       search=lambda query: MARKET_PAGES)
    return steps["research_market"](STATE)


def test_country_figures_come_before_wider_ones():
    result = market_step(
        figure("USD 9.5 billion", "wider", "https://eu.example/report", area="Europe"),
        figure("EUR 1.2 billion", "country", "https://de.example/report"))

    assert [f.scope for f in result["market_figures"]] == ["country", "wider"]
    assert result["log"] == ["Market: 2 figures, 1 for Germany itself"]


def test_a_wider_figure_keeps_its_label_and_is_never_relabelled_as_the_country():
    result = market_step(
        figure("USD 9.5 billion", "wider", "https://eu.example/report", area="Europe"))

    assert result["market_figures"][0].area == "Europe"
    assert result["market_figures"][0].scope == "wider"


def test_a_figure_that_is_not_in_its_source_is_dropped():
    result = market_step(figure("EUR 5 billion", "country", "https://de.example/report"))

    assert result["market_figures"] == []


def test_a_figure_from_an_invented_source_is_dropped():
    result = market_step(figure("EUR 1.2 billion", "country", "https://invented.example"))

    assert result["market_figures"] == []


def test_a_figure_for_a_different_country_is_dropped():
    result = market_step(figure("EUR 1.2 billion", "other", "https://de.example/report",
                                area="Austria"))

    assert result["market_figures"] == []


def test_no_market_search_results_gives_an_empty_list():
    steps = make_steps(search=lambda query: [])

    assert steps["research_market"](STATE)["market_figures"] == []


# --- step 7: news --------------------------------------------------------------------------

NEWS_PAGES = [page("https://news.example/a", "HelloFresh expands", "New plant in Germany")]


def test_news_items_with_a_real_source_are_kept():
    answer = NewsList(items=[
        NewsItem(summary="HelloFresh opens a plant.", date="2026-11-01",
                 source_url="https://news.example/a"),
        NewsItem(summary="Invented story.", date="2026-11-02",
                 source_url="https://invented.example/b")])
    steps = make_steps(answers={NewsList: answer}, news=lambda query: NEWS_PAGES)

    result = steps["research_news"](STATE)

    assert [item.summary for item in result["news"]] == ["HelloFresh opens a plant."]


def test_no_news_results_gives_an_empty_list():
    steps = make_steps(news=lambda query: [])

    assert steps["research_news"](STATE) == {"news": [], "log": ["News: no results"]}


# --- step 7: the demand trend -------------------------------------------------------------------

def trend_series(values: list[float]) -> TrendSeries:
    points = [(f"2026-{month:02d}", value) for month, value in enumerate(values, start=1)]
    return TrendSeries(label="Search interest", unit="index", points=points,
                       url="https://t.example", low_volume_below=10)


BUSY = trend_series([40, 45, 50, 55, 60, 60, 65, 70, 70, 75, 80, 80])
QUIET = trend_series([2, 3, 2, 3, 100, 2, 3, 2, 3, 2, 3, 2])


def trend_step(data: dict, terms: list[str] | None = None,
               too_broad: list[str] | None = None) -> dict:
    tried = []

    def trend(term, country):
        tried.append(term)
        return data.get(term)

    def ask(schema, instructions, material):
        # The fake model calls a word too broad if the test listed it.
        word = material.split(chr(10))[0].removeprefix("Search word: ")
        return TermCheck(specific=word not in (too_broad or []), reason="test")

    brief = BRIEF.model_copy(update={"trend_terms": terms or BRIEF.trend_terms})
    steps = research.make_research_steps(Deps(
        ask=ask, search=lambda query: [], news=lambda query: [],
        read_page=lambda url: None, financials=lambda name: None, trend=trend))
    result = steps["research_trend"]({**STATE, "brief": brief})
    result["tried"] = tried
    return result


def test_the_first_term_with_enough_searches_is_used():
    result = trend_step({"Kochbox": BUSY, "Fertiggerichte": BUSY})

    assert result["trend"].term == "Kochbox"
    assert result["trend"].reliable
    assert result["tried"] == ["Kochbox"]            # no need to try the others


def test_a_low_volume_term_is_skipped_when_a_better_one_exists():
    result = trend_step({"Kochbox": QUIET, "Fertiggerichte": BUSY})

    assert result["trend"].term == "Fertiggerichte"
    assert result["trend"].reliable


def test_low_volume_data_is_kept_but_marked_unreliable_when_nothing_better_exists():
    result = trend_step({"Kochbox": QUIET})

    assert result["trend"].term == "Kochbox"
    assert not result["trend"].reliable
    assert "Reliability: low" in result["trend"].summary


def test_no_data_for_any_term_gives_no_trend():
    result = trend_step({})

    assert result["trend"] is None
    assert result["tried"] == ["Kochbox", "Fertiggerichte", "Essenslieferung"]


def test_short_broad_words_and_phrases_are_never_measured():
    result = trend_step({"Bio": BUSY, "gesunde Mahlzeit": BUSY, "Kochbox": BUSY},
                        terms=["Bio", "gesunde Mahlzeit", "Kochbox"])

    assert result["tried"] == ["Kochbox"]
    assert result["trend"].term == "Kochbox"


def test_a_word_the_model_judges_too_broad_is_not_measured():
    result = trend_step({"Mahlzeit": BUSY, "Kochbox": BUSY},
                        terms=["Mahlzeit", "Kochbox"], too_broad=["Mahlzeit"])

    assert result["tried"] == ["Kochbox"]
    assert result["trend"].term == "Kochbox"


def test_when_every_word_is_too_broad_there_is_no_trend_and_the_log_says_why():
    result = trend_step({"Mahlzeit": BUSY}, terms=["Mahlzeit"], too_broad=["Mahlzeit"])

    assert result["trend"] is None
    assert result["tried"] == []
    assert result["log"] == ["Demand trend: no usable search word (too broad: Mahlzeit)"]


def test_a_region_that_is_not_one_country_gives_no_trend():
    result = make_steps()["research_trend"]({**STATE, "country": "Europe"})

    assert result["trend"] is None
