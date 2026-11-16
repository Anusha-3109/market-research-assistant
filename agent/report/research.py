"""Steps 4 to 7 of the report workflow: collect the facts.

4 and 5. For each competitor: public figures, and prices read from the
         competitor's own website.
6.       Market figures, each labelled with the area and year it covers.
7.       Recent news and the demand trend.

The same rule applies as in the earlier steps: code gathers the material and
checks the answer; the model does one narrow extraction job in between. In
particular, the SOURCE of every price is set by code to the page that was
actually opened, so a price can never be attributed to the wrong site.
"""

import re
from urllib.parse import urlsplit

from agent.config import PAGE_MAX_CHARS
from agent.countries import find_country
from agent.report.deps import Deps
from agent.report.state import (
    Competitor,
    CompetitorProfile,
    MarketFigureList,
    NewsList,
    PriceList,
    ReportState,
    TermCheck,
    TrendResult,
)
from agent.report.steps import (
    clean_url,
    is_own_site,
    known_url,
    merge_results,
    titles_of,
)
from agent.tools import format_results
from agent.trends import is_low_volume, summarise

# Words in a web address that suggest the page shows prices or products.
# They are compared with whole words of the address, so "abo" (German for
# subscription) does not match "about".
PRICE_PAGE_WORDS = {
    "preis", "preise", "price", "prices", "pricing", "plan", "plans",
    "tarif", "tarife", "kosten", "cost", "costs", "abo", "shop", "product",
    "products", "produkt", "produkte", "menu", "collections", "bestellen",
    "order",
}
MAX_PRICE_PAGES = 3
MAX_PRICES = 5
MAX_MARKET_FIGURES = 6
MAX_NEWS = 5
MAX_TREND_TERMS = 3
MIN_TREND_TERM_LENGTH = 6

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


# --- checks on the model's answers ------------------------------------------------------

def numbers_in(text: str) -> list[str]:
    return NUMBER.findall(text or "")


def same_number(number: str) -> str:
    """Write a number one way, so 7,99 and 7.99 compare equal."""
    return number.replace(",", ".")


def is_quoted_from(value: str, text: str) -> bool:
    """True if the value contains at least one number and every number in
    it appears in the text as a whole number. This catches a figure the
    model made up or changed instead of copying.

    Whole numbers are compared, not characters: "5" must not match because
    the text contains "2025".
    """
    wanted = {same_number(number) for number in numbers_in(value)}
    present = {same_number(number) for number in numbers_in(text)}
    return bool(wanted) and wanted <= present


def rank_price_pages(urls: list[str]) -> list[str]:
    """Put pages whose address hints at prices first, keep the order
    otherwise, and drop duplicates."""
    unique = list(dict.fromkeys(clean_url(url) for url in urls if url))

    def looks_like_a_price_page(url: str) -> bool:
        # Only the part after the host counts: "shop" in "myshop.com" says
        # nothing about the page.
        parts = urlsplit(url)
        words = re.findall(r"[a-z]+", f"{parts.path} {parts.query}".lower())
        return any(word in PRICE_PAGE_WORDS for word in words)

    return sorted(unique, key=lambda url: not looks_like_a_price_page(url))


def source_link(figures_text: str) -> str:
    """Pull the 'Source: <link>' line out of the financials text."""
    match = re.search(r"^Source: (\S+)", figures_text, flags=re.MULTILINE)
    return match.group(1) if match else ""


# --- the steps ---------------------------------------------------------------------------

def make_research_steps(deps: Deps) -> dict:

    def find_prices(competitor: Competitor, task: dict):
        """Open the competitor's own pages until one shows prices.

        Returns (prices, the page they came from, a note if none found).
        """
        name = competitor.name
        results = deps.search(f"{name} {task['price_word']} {task['country']}")
        own_pages = [r.get("url", "") for r in results
                     if is_own_site(name, r.get("url", ""))]
        pages = rank_price_pages(own_pages + [competitor.shop_url])[:MAX_PRICE_PAGES]
        if not pages:
            return [], "", "the company's own website was not found"

        opened_any = False
        for url in pages:
            text = deps.read_page(url)
            if not text:
                continue
            opened_any = True
            text = text[:PAGE_MAX_CHARS]

            answer = deps.ask(
                PriceList,
                f"This is the text of a page from the website of {name}. List "
                f"up to {MAX_PRICES} prices of its main products or plans. "
                f"Copy each price exactly as written, with its currency. Only "
                f"list prices that appear in this text. Skip shipping fees, "
                f"discounts and vouchers. If the text shows no prices, return "
                f"an empty list.",
                text,
            )
            # Keep only prices whose numbers really are on the page.
            prices = [price for price in answer.prices
                      if is_quoted_from(price.price, text)][:MAX_PRICES]
            if prices:
                return prices, url, ""

        if not opened_any:
            return [], "", "the company's website could not be read"
        return [], "", "no prices are shown on the pages that were read"

    def research_competitor(task: dict) -> dict:
        """Steps 4 and 5, run once per competitor in parallel."""
        competitor: Competitor = task["competitor"]

        figures = deps.financials(competitor.name) or ""
        prices, price_source, price_note = find_prices(competitor, task)

        profile = CompetitorProfile(
            name=competitor.name,
            shop_url=competitor.shop_url,
            figures=figures,
            figures_source=source_link(figures),
            prices=prices,
            price_source=price_source,
            price_note=price_note,
        )
        found = f"{len(prices)} prices from {price_source}" if prices else f"no prices ({price_note})"
        # Names for this competitor's pages in the app's source list.
        titles = {}
        if profile.shop_url:
            titles[clean_url(profile.shop_url)] = f"{competitor.name}: website"
        if price_source:
            titles[clean_url(price_source)] = f"{competitor.name}: prices"
        if profile.figures_source:
            titles[clean_url(profile.figures_source)] = f"{competitor.name}: company figures"
        return {
            "profiles": [profile],
            "titles": titles,
            "log": [f"{competitor.name}: figures {'found' if figures else 'not found'}, {found}"],
        }

    def research_market(state: ReportState) -> dict:
        """Step 6: market size and growth, each with its area and year."""
        product, country, brief = state["product"], state["country"], state["brief"]
        results = merge_results([
            deps.search(f"{product} market size {country}"),
            deps.search(brief.market_query),
        ])
        if not results:
            return {"market_figures": [], "log": ["Market: no search results"]}

        answer = deps.ask(
            MarketFigureList,
            f"Extract market size, growth and customer figures about "
            f"{product} from these search results. The target country is "
            f"{country}. For each figure, state exactly which area and year "
            f"it covers as the source says. Many sources report Europe or "
            f"the world: mark those 'wider', never 'country'. Copy each "
            f"value exactly. Only use figures that appear in the results.",
            format_results(results),
        )

        by_url = {clean_url(r.get("url", "")): r for r in results}
        kept = []
        for figure in answer.figures:
            page = by_url.get(clean_url(figure.source_url))
            if page is None or figure.scope == "other":
                continue
            if not is_quoted_from(figure.value, f"{page.get('title', '')} {page.get('content', '')}"):
                continue
            kept.append(figure)

        # Figures for the country itself first.
        kept.sort(key=lambda figure: figure.scope != "country")
        kept = kept[:MAX_MARKET_FIGURES]
        country_count = sum(figure.scope == "country" for figure in kept)
        return {
            "market_figures": kept,
            "titles": titles_of(results),
            "log": [f"Market: {len(kept)} figures, {country_count} for {country} itself"],
        }

    def research_news(state: ReportState) -> dict:
        """Step 7a: recent news about this market in this country."""
        product, country, brief = state["product"], state["country"], state["brief"]
        results = merge_results([
            deps.news(f"{product} {country}"),
            deps.news(f"{brief.category_terms[0]} {country}"),
        ])
        if not results:
            return {"news": [], "log": ["News: no results"]}

        answer = deps.ask(
            NewsList,
            f"From these news results, pick up to {MAX_NEWS} that are about "
            f"the {product} market in {country}: launches, closures, "
            f"funding, regulation or changes in what customers want. Leave "
            f"out anything about other countries or other industries. If "
            f"none qualify, return an empty list.",
            format_results(results),
        )
        items = [item for item in answer.items
                 if known_url(item.source_url, results)][:MAX_NEWS]
        return {"news": items, "titles": titles_of(results),
                "log": [f"News: {len(items)} relevant items"]}

    def research_trend(state: ReportState) -> dict:
        """Step 7b: the demand trend. Several search words are tried and
        the first one with enough searches to be trusted is used."""
        country = find_country(state["country"])
        if country is None:
            return {"trend": None,
                    "log": [f"Demand trend: '{state['country']}' is not a single country"]}

        fallback = None
        skipped = []
        trend_titles: dict[str, str] = {}
        for term in state["brief"].trend_terms[:MAX_TREND_TERMS]:
            # Very short words ("Bio", "Diät") are almost always too broad
            # to say anything about one product category.
            if len(term) < MIN_TREND_TERM_LENGTH or " " in term.strip():
                skipped.append(term)
                continue
            # A separate yes-or-no question. Asked to pick search words, the
            # model chose broad ones such as "Mahlzeit" (meal); asked to
            # judge one word, it is far more reliable.
            check = deps.ask(
                TermCheck,
                "You judge whether a search word is specific to a product "
                "category. Answer strictly.",
                f"Search word: {term}\nCountry: {country.name}\n"
                f"Product category: {state['product']}\n"
                f"Would most people who type this word into a search engine "
                f"be looking to buy or order this product? Words with "
                f"everyday meanings (a greeting, a general food word, an "
                f"adjective) are not specific.",
            )
            if not check.specific:
                skipped.append(term)
                continue
            series = deps.trend(term, country)
            if series is None:
                continue
            trend_titles[clean_url(series.url)] = f"Search interest for '{term}'"
            result = TrendResult(term=term, summary=summarise(series),
                                 reliable=not is_low_volume(series))
            if result.reliable:
                return {"trend": result, "titles": trend_titles,
                        "log": [f"Demand trend: measured with '{term}'"]}
            fallback = fallback or result

        if fallback:
            return {"trend": fallback, "titles": trend_titles,
                    "log": [f"Demand trend: only low-volume data, for '{fallback.term}'"]}
        note = f" (too broad: {', '.join(skipped)})" if skipped else ""
        return {"trend": None,
                "log": [f"Demand trend: no usable search word{note}"]}

    def collect_facts(state: ReportState) -> dict:
        """Meeting point for the parallel branches. Puts the competitor
        profiles back in the order the competitors were ranked."""
        order = {c.name: position for position, c in enumerate(state.get("competitors", []))}
        profiles = sorted(state.get("profiles", []),
                          key=lambda profile: order.get(profile.name, len(order)))
        with_prices = sum(bool(profile.prices) for profile in profiles)
        return {"log": [f"Facts collected: {len(profiles)} competitors, "
                        f"{with_prices} with first-hand prices"]}

    return {
        "research_competitor": research_competitor,
        "research_market": research_market,
        "research_news": research_news,
        "research_trend": research_trend,
        "collect_facts": collect_facts,
    }
