"""Google News RSS feed: backup news search. No key needed."""

import feedparser

from agent.config import NEWS_DAYS, SEARCH_MAX_RESULTS
from agent.sources import http

FEED_URL = "https://news.google.com/rss/search"


def search_news(query: str) -> list[dict]:
    """Search news articles from the last NEWS_DAYS days."""
    response = http.get(FEED_URL, params={
        "q": f"{query} when:{NEWS_DAYS}d",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })
    feed = feedparser.parse(response.text)

    results = []
    for entry in feed.entries[:SEARCH_MAX_RESULTS]:
        outlet = entry.get("source", {}).get("title") or "Unknown outlet"
        results.append({
            "title": entry.get("title"),
            # A Google News link that redirects to the original article.
            "url": entry.get("link"),
            # The feed carries headlines only, no article text.
            "content": f"{outlet}: headline only, no extract available.",
            "published_date": entry.get("published"),
        })
    return results
