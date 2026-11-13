"""Free web metasearch through the `ddgs` library: backup web search and
backup news search. No key needed.

`ddgs` queries public search engines directly. Each engine on its own is
unreliable (it often answers "no results" when it is rate limiting), so
search() tries several engines in turn and returns the first real answer.
"""

from ddgs import DDGS

from agent.config import SEARCH_MAX_RESULTS
from agent.sources import SourceError

# Tried in this order until one returns results.
SEARCH_ENGINES = ["bing", "yahoo", "google", "duckduckgo"]


def search(query: str) -> list[dict]:
    """Search the web, trying each engine until one returns results."""
    errors = []
    for engine in SEARCH_ENGINES:
        try:
            hits = DDGS().text(query, max_results=SEARCH_MAX_RESULTS, backend=engine)
        except Exception as error:  # network problem, rate limit, no results
            errors.append(f"{engine}: {error}")
            continue
        if hits:
            return [
                {"title": hit.get("title"), "url": hit.get("href"),
                 "content": hit.get("body")}
                for hit in hits
            ]
        errors.append(f"{engine}: no results")

    raise SourceError("; ".join(errors))


def search_news(query: str) -> list[dict]:
    """Search news articles from about the last month."""
    try:
        hits = DDGS().news(query, max_results=SEARCH_MAX_RESULTS, timelimit="m")
    except Exception as error:
        raise SourceError(str(error)) from error

    return [
        {
            "title": hit.get("title"),
            "url": hit.get("url"),
            "content": f"{hit.get('source') or 'Unknown outlet'}: {hit.get('body') or ''}",
            "published_date": hit.get("date"),
        }
        for hit in hits or []
    ]
