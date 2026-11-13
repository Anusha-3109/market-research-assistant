"""Tools the agent can call.

A tool is a normal Python function with the @tool decorator. The model never
runs it. The model only asks for it by name with arguments; LangChain runs
the function and passes the returned text back to the model.

Every tool returns text, including when something goes wrong. An error
message as text lets the agent react (retry, or tell the user) and keeps
the app running.
"""

import re
from datetime import date
from pathlib import Path

from langchain.tools import ToolRuntime, tool

from agent.config import (
    PAGE_MAX_CHARS,
    REPORT_HEADING,
    REPORTS_DIR,
    SNIPPET_MAX_CHARS,
)
from agent.countries import find_country
from agent.fallback import try_sources
from agent.sources import (
    SourceError,
    metasearch,
    google_news,
    google_trends,
    tavily,
    webpage,
    wikidata,
    wikipedia,
    yahoo,
)
from agent.trends import summarise


# ---------------------------------------------------------------------------
# Web and news search
# ---------------------------------------------------------------------------

def format_results(results: list[dict]) -> str:
    """Turn raw search results into numbered text the model can cite from."""
    if not results:
        return "No results found. Try a different or more specific query."

    blocks = []
    for number, item in enumerate(results, start=1):
        title = item.get("title") or "Untitled"
        url = item.get("url") or "no url"
        # Collapse whitespace and cap the length: some pages return long
        # menus or lists that waste the model's attention.
        snippet = " ".join((item.get("content") or "").split())[:SNIPPET_MAX_CHARS]
        lines = [f"[{number}] {title}", f"URL: {url}"]
        if item.get("published_date"):
            lines.append(f"Published: {item['published_date']}")
        lines.append(snippet)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# Each list is tried in order: the first source that answers wins. Backups
# are added here as they are built.
WEB_SEARCH_SOURCES = [
    ("Tavily", tavily.search),
    ("Web metasearch", metasearch.search),
    ("Wikipedia", wikipedia.search),
]
NEWS_SOURCES = [
    ("Tavily", tavily.search_news),
    ("Google News", google_news.search_news),
    ("Metasearch news", metasearch.search_news),
]


def run_search(sources: list, query: str) -> str:
    """Try the sources in order and return formatted results that start
    with a line naming the source, or a readable message if all fail."""
    outcome = try_sources(sources, query)
    if not outcome.succeeded:
        return (
            f"Search failed. {outcome.source_note()}. Try a different query, "
            "or tell the user this information could not be retrieved."
        )
    return f"{outcome.source_note()}\n\n{format_results(outcome.value)}"


@tool
def web_search(query: str) -> str:
    """Search the web for information about a market, industry, competitor
    or price.

    Use this for market size, competitor names, product details and prices.
    Each result has a title, a URL and a short extract. Cite the URL when
    you use a fact from a result. For recent events use search_news instead.

    Args:
        query: A focused search query of 3 to 10 words that includes the
            country or region, for example "meal kit delivery competitors
            Germany".
    """
    return run_search(WEB_SEARCH_SOURCES, query)


@tool
def search_news(query: str) -> str:
    """Search recent news articles (about the last month) about an industry
    or a company.

    Use this for the Trends section: new launches, funding, regulation,
    closures and changes in customer behaviour. Each result has a title, a
    URL, a publication date and a short extract. Do not use it for prices or
    market size; use web_search for those.

    Args:
        query: A focused news query of 3 to 10 words, for example
            "meal delivery Germany funding".
    """
    return run_search(NEWS_SOURCES, query)


# ---------------------------------------------------------------------------
# Reading one web page
# ---------------------------------------------------------------------------

PAGE_SOURCES = [
    ("Tavily Extract", tavily.read_page),
    ("Direct fetch", webpage.fetch),
]


@tool
def read_webpage(url: str) -> str:
    """Open one web page and read its full text.

    Use this to get facts first-hand, above all a competitor's own pricing
    or product page. Search results only show a short extract; this returns
    the whole page. Only pass a URL that appeared in a search result or that
    the user gave you.

    Args:
        url: The full address of the page, starting with http:// or https://.
    """
    # Checked here, before any source runs, so a blocked address is never
    # sent anywhere and the model gets one clear reason.
    try:
        webpage.check_url(url)
    except webpage.UnsafeUrlError as error:
        return f"This page cannot be opened: {error}."

    outcome = try_sources(PAGE_SOURCES, url)
    if not outcome.succeeded:
        return (
            f"The page could not be read. {outcome.source_note()}. Use the "
            "search extract instead, or report the detail as 'not found'."
        )

    text = outcome.value
    shortened = len(text) > PAGE_MAX_CHARS
    note = " (page shortened)" if shortened else ""
    return f"{outcome.source_note()}{note}\nURL: {url}\n\n{text[:PAGE_MAX_CHARS]}"


# ---------------------------------------------------------------------------
# Demand trend
# ---------------------------------------------------------------------------

TREND_SOURCES = [
    ("Google Trends", google_trends.interest),
    ("Wikipedia pageviews", wikipedia.pageviews),
]


@tool
def get_demand_trend(term: str, country: str) -> str:
    """Find out whether public interest in a product or category has been
    rising, falling or stable over the last 12 months.

    Use this once per report for the Trends section. It returns the
    direction, the percentage change and the source. The figures measure
    interest (searches or page views), not sales or market size.

    Args:
        term: A short, common name for the product, 1 to 3 words, as people
            in that country would type it into a search engine, in their
            own language, for example "Kochbox" for meal kits in Germany.
        country: The country name in English, for example "Germany".
    """
    found = find_country(country)
    if found is None:
        return (
            f"The country '{country}' was not recognised. Call this tool "
            "again with the English name of one country, for example "
            "'Germany'."
        )

    outcome = try_sources(TREND_SOURCES, term, found)
    if not outcome.succeeded:
        return (
            f"No trend data found. {outcome.source_note()}. Try a shorter, "
            "more common term, or report the demand trend as 'not found'."
        )
    return f"{outcome.source_note()}\n{summarise(outcome.value)}"


# ---------------------------------------------------------------------------
# Company financials
# ---------------------------------------------------------------------------

# Legal forms and country words that are not part of a brand name.
LEGAL_WORDS = {
    "gmbh", "ag", "se", "kg", "co", "ug", "ohg", "inc", "ltd", "llc", "plc",
    "corp", "corporation", "limited", "sa", "sas", "bv", "nv", "ab", "oy",
    "group", "holding", "holdings", "deutschland", "germany", "international",
}


def brand_name(company: str) -> str:
    """Strip legal forms from a company name:
    'HelloFresh Deutschland GmbH & Co. KG' -> 'HelloFresh'."""
    words = re.findall(r"[^\W_]+", company)
    kept = [word for word in words if word.lower() not in LEGAL_WORDS]
    return " ".join(kept) or company


FINANCIAL_SOURCES = [
    ("Yahoo Finance", yahoo.company_financials),
    ("Wikidata", wikidata.company_facts),
]


@tool
def get_company_financials(company: str) -> str:
    """Get public figures about a company: revenue, employees, market value,
    sector, country and founding year.

    It reads Yahoo Finance for stock-market-listed companies, and Wikidata
    for others. Many small private companies are in neither; the tool then
    says so and you should report "not found". Wikidata figures can be years
    old, so always quote the year shown next to a figure.

    Args:
        company: The brand name people know the company by, for example
            "HelloFresh", not the legal name of a local subsidiary.
    """
    outcome = try_sources(FINANCIAL_SOURCES, company)

    # The model sometimes passes a legal name such as "HelloFresh
    # Deutschland GmbH & Co. KG", which no source lists. Try the brand name.
    brand = brand_name(company)
    if not outcome.succeeded and brand != company:
        retry = try_sources(FINANCIAL_SOURCES, brand)
        if retry.succeeded:
            outcome, company = retry, brand
    # "no results" means the source worked but does not know the company.
    if outcome.succeeded:
        note = outcome.source_note()
        if outcome.failures == [("Yahoo Finance", "no results")]:
            note = f"Source used: {outcome.used} (not listed on Yahoo Finance)"
        return f"{note}\n{outcome.value}"

    if all(reason == "no results" for _, reason in outcome.failures):
        return (
            f"No public figures found for '{company}' in Yahoo Finance or "
            "Wikidata. It is probably a small private company. Report this "
            "as 'not found'."
        )
    return (
        f"Financial lookup failed. {outcome.source_note()}. Report this as "
        "'not found'."
    )


# ---------------------------------------------------------------------------
# Saving a report
# ---------------------------------------------------------------------------

def safe_filename(title: str) -> str:
    """Turn a report title into a safe file name.

    Only letters, digits and hyphens survive, so a title can never contain
    a path such as '../' and the file always stays inside the reports folder.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-")
    return f"{date.today().isoformat()}-{slug or 'report'}.md"


def write_report(title: str, content: str, folder: Path) -> Path:
    """Write a report into the given folder and return the file path."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_filename(title)
    path.write_text(content, encoding="utf-8")
    return path


def find_last_report(messages: list) -> str | None:
    """Return the most recent report the assistant wrote, or None.

    A report is an assistant message that contains the report heading. The
    text is taken from the heading onwards.
    """
    for message in reversed(messages):
        content = getattr(message, "content", "")
        if getattr(message, "type", "") == "ai" and isinstance(content, str):
            position = content.find(REPORT_HEADING)
            if position != -1:
                return content[position:].strip()
    return None


def save_latest_report(title: str, messages: list, folder: Path) -> str:
    """Save the latest report in the conversation and describe the result."""
    report = find_last_report(messages)
    if report is None:
        return ("Nothing was saved: there is no report in this conversation "
                "yet. Write the report first, then save it.")
    try:
        path = write_report(title, report, folder)
    except OSError as error:
        return f"Saving failed: {error}."
    return f"Report saved to reports/{path.name}"


@tool
def save_report(title: str, runtime: ToolRuntime) -> str:
    """Save the most recent market research report in this conversation to
    a markdown file.

    Only use this when the user asks to save the report. The tool copies the
    report exactly as it was shown to the user, so you only pass a title.

    Args:
        title: A short title, for example "Healthy meal delivery Germany".
    """
    # The report is read from the conversation state rather than passed in
    # by the model. Retyping a long report as a tool argument costs tokens
    # and was seen to corrupt characters such as the euro sign and umlauts.
    return save_latest_report(title, runtime.state["messages"], REPORTS_DIR)


TOOLS = [
    web_search,
    search_news,
    read_webpage,
    get_demand_trend,
    get_company_financials,
    save_report,
]
