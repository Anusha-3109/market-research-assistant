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

import yfinance as yf
from langchain.tools import ToolRuntime, tool
from langchain_tavily import TavilySearch

from agent.config import (
    NEWS_TIME_RANGE,
    REPORT_HEADING,
    REPORTS_DIR,
    SEARCH_MAX_RESULTS,
    SNIPPET_MAX_CHARS,
)


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


def run_search(query: str, **options) -> str:
    """Call Tavily and return formatted results, or a readable error."""
    try:
        search = TavilySearch(max_results=SEARCH_MAX_RESULTS, **options)
        response = search.invoke({"query": query})
    except Exception as error:  # network problem, bad key, rate limit
        return f"Search failed: {error}. Try again or use a different query."

    if isinstance(response, dict) and response.get("error"):
        return f"Search failed: {response['error']}."

    results = response.get("results", []) if isinstance(response, dict) else []
    return format_results(results)


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
    return run_search(query)


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
    return run_search(query, topic="news", time_range=NEWS_TIME_RANGE)


# ---------------------------------------------------------------------------
# Company financials
# ---------------------------------------------------------------------------

def format_money(value, currency: str) -> str:
    """Format a large number as, for example, '7.6 billion EUR'."""
    if not isinstance(value, (int, float)):
        return "not found"
    for size, name in ((1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
        if abs(value) >= size:
            return f"{value / size:.1f} {name} {currency}".strip()
    return f"{value:,.0f} {currency}".strip()


def lookup_financials(company: str) -> str:
    """Find a listed company by name and return its key public figures."""
    not_listed = (
        f"No listed company found for '{company}'. It is probably a private "
        "company, so no public financials are available. Report this as "
        "'not found'."
    )

    quotes = yf.Search(company, max_results=5).quotes
    shares = [quote for quote in quotes if quote.get("quoteType") == "EQUITY"]
    if not shares:
        return not_listed

    symbol = shares[0]["symbol"]
    info = yf.Ticker(symbol).info or {}
    name = info.get("longName") or shares[0].get("shortname") or symbol
    price_currency = info.get("currency") or ""
    report_currency = info.get("financialCurrency") or price_currency
    employees = info.get("fullTimeEmployees")

    return "\n".join([
        f"Company: {name} (ticker {symbol})",
        f"Sector: {info.get('sector') or 'not found'}",
        f"Industry: {info.get('industry') or 'not found'}",
        f"Country: {info.get('country') or 'not found'}",
        f"Revenue (last 12 months): "
        f"{format_money(info.get('totalRevenue'), report_currency)}",
        f"Market value: {format_money(info.get('marketCap'), price_currency)}",
        f"Employees: {employees if employees else 'not found'}",
        f"Source: https://finance.yahoo.com/quote/{symbol}",
        f"Retrieved: {date.today().isoformat()}",
        "Check that the company name above is the company you meant. If it "
        "is a different company, ignore this result and report 'not found'.",
    ])


@tool
def get_company_financials(company: str) -> str:
    """Get public financial figures for a stock-market-listed company:
    revenue, market value, employees, sector and country, from Yahoo Finance.

    Use this for large competitors that are listed on a stock exchange.
    Small and private companies have no public financials; for those the
    tool says so and you should report "not found".

    Args:
        company: The company name, for example "HelloFresh".
    """
    try:
        return lookup_financials(company)
    except Exception as error:  # network problem or unexpected data
        return f"Financial lookup failed: {error}. Report this as 'not found'."


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


TOOLS = [web_search, search_news, get_company_financials, save_report]
