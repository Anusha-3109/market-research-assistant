"""Wikipedia: last-resort web search, and page-view counts as a backup
measure of interest in a topic. No key needed.

Wikipedia cannot replace a web search, but when every search engine is
down it still gives sourced background on an industry or a large company.
"""

import re
from datetime import date
from urllib.parse import quote

from agent.config import SEARCH_MAX_RESULTS
from agent.sources import SourceError, http
from agent.trends import TrendSeries

API_URL = "https://en.wikipedia.org/w/api.php"
PAGEVIEWS_URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                 "en.wikipedia/all-access/user/{article}/monthly/{start}/{end}")


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


def last_12_full_months(today: date) -> tuple[str, str]:
    """Return the first day of the month 12 months ago and the first day of
    the current month, as YYYYMMDD00. The current month is left out because
    it is not finished."""
    end = today.replace(day=1)
    start = end.replace(year=end.year - 1)
    return start.strftime("%Y%m%d00"), end.strftime("%Y%m%d00")


def pageviews(term: str, country=None) -> TrendSeries:
    """Return monthly views of the Wikipedia article that best matches a
    term, for the last 12 full months.

    `country` is accepted so this can stand in for a per-country source, but
    Wikipedia only counts views worldwide, so it is not used.
    """
    articles = search(term)
    if not articles:
        raise SourceError("no matching Wikipedia article")
    title = articles[0]["title"].removesuffix(" (Wikipedia)")
    article = quote(title.replace(" ", "_"), safe="")

    start, end = last_12_full_months(date.today())
    response = http.get(PAGEVIEWS_URL.format(article=article, start=start, end=end))
    try:
        items = response.json()["items"]
        points = [(f"{item['timestamp'][:4]}-{item['timestamp'][4:6]}",
                   float(item["views"])) for item in items]
    except (ValueError, KeyError) as error:
        raise SourceError("unexpected response from Wikipedia pageviews") from error

    # The last item can be the unfinished current month; drop it.
    this_month = date.today().strftime("%Y-%m")
    points = [point for point in points if point[0] != this_month]
    if len(points) < 4:
        raise SourceError("not enough page-view history")

    return TrendSeries(
        label=f"Views of the English Wikipedia article '{title}'",
        unit="page views per month by people (not bots)",
        points=points,
        url=f"https://pageviews.wmcloud.org/?project=en.wikipedia.org&pages={article}",
        note="worldwide figure for English-language readers, not specific to "
             "one country. Check that the article matches the product; if it "
             "does not, do not use this figure.",
    )
