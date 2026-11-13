"""Tavily: web search, news search and page reading. Needs TAVILY_API_KEY."""

from langchain_tavily import TavilyExtract, TavilySearch

from agent.config import NEWS_TIME_RANGE, SEARCH_MAX_RESULTS
from agent.sources import SourceError


def _run(query: str, **options) -> list[dict]:
    """Call Tavily and return its list of results."""
    try:
        search = TavilySearch(max_results=SEARCH_MAX_RESULTS, **options)
        response = search.invoke({"query": query})
    except Exception as error:  # network problem, bad key, rate limit
        raise SourceError(str(error)) from error

    if not isinstance(response, dict):
        raise SourceError(f"unexpected response: {response}")
    if response.get("error"):
        raise SourceError(str(response["error"]))
    return response.get("results", [])


def search(query: str) -> list[dict]:
    """Search the web."""
    return _run(query)


def search_news(query: str) -> list[dict]:
    """Search recent news articles."""
    return _run(query, topic="news", time_range=NEWS_TIME_RANGE)


def read_page(url: str) -> str:
    """Return the text of one web page, read through Tavily Extract."""
    try:
        response = TavilyExtract().invoke({"urls": [url]})
    except Exception as error:
        raise SourceError(str(error)) from error

    if not isinstance(response, dict):
        raise SourceError(f"unexpected response: {response}")
    if response.get("error"):
        raise SourceError(str(response["error"]))
    results = response.get("results") or []
    if not results:
        failed = response.get("failed_results") or []
        reason = failed[0].get("error") if failed else "no content returned"
        raise SourceError(str(reason))
    return (results[0].get("raw_content") or "").strip()
