"""Wikipedia: last-resort web search. No key needed.

Wikipedia cannot replace a web search, but when every search engine is
down it still gives sourced background on an industry or a large company.
"""

import re
from urllib.parse import quote

from agent.config import SEARCH_MAX_RESULTS
from agent.sources import SourceError, http

API_URL = "https://en.wikipedia.org/w/api.php"


def _strip_html(text: str) -> str:
    """Remove the highlight tags Wikipedia puts around matched words."""
    return re.sub(r"<[^>]+>", "", text or "")


def search(query: str) -> list[dict]:
    """Search Wikipedia articles."""
    response = http.get(API_URL, params={
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": SEARCH_MAX_RESULTS,
        "format": "json",
    })
    try:
        hits = response.json()["query"]["search"]
    except (ValueError, KeyError) as error:
        raise SourceError("unexpected response from Wikipedia") from error

    return [
        {
            "title": f"{hit['title']} (Wikipedia)",
            "url": "https://en.wikipedia.org/wiki/" + quote(hit["title"].replace(" ", "_")),
            "content": _strip_html(hit.get("snippet")),
        }
        for hit in hits
    ]
