"""Tests for the backup sources, using fake responses (no internet).

Each test checks that a source turns its service's reply into the common
result shape: title, url, content and, for news, published_date.
"""

import pytest
import requests

from agent.sources import SourceError, google_news, http, metasearch, wikipedia


class FakeResponse:
    """Stands in for a web response."""

    def __init__(self, json_data=None, text="", ok=True, status_code=200):
        self._json = json_data
        self.text = text
        self.ok = ok
        self.status_code = status_code

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


# --- shared web requests ------------------------------------------------------

def test_http_get_treats_a_rate_limit_as_a_failure(monkeypatch):
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: FakeResponse(ok=False, status_code=429))

    with pytest.raises(SourceError, match="HTTP 429"):
        http.get("https://example.com")


def test_http_get_treats_a_network_error_as_a_failure(monkeypatch):
    def no_network(*args, **kwargs):
        raise requests.ConnectionError("no internet")

    monkeypatch.setattr(requests, "get", no_network)

    with pytest.raises(SourceError, match="no internet"):
        http.get("https://example.com")


# --- Metasearch ---------------------------------------------------------------

class FakeDDGS:
    def text(self, query, max_results, backend):
        return [{"title": "Meal kits", "href": "https://m.example", "body": "About kits"}]

    def news(self, query, max_results, timelimit):
        return [{"title": "Kit news", "url": "https://n.example", "body": "Story",
                 "source": "The Paper", "date": "2026-11-03"}]


def test_metasearch_search_returns_the_common_shape(monkeypatch):
    monkeypatch.setattr(metasearch, "DDGS", FakeDDGS)

    assert metasearch.search("meal kits") == [
        {"title": "Meal kits", "url": "https://m.example", "content": "About kits"}
    ]


def test_metasearch_news_includes_the_outlet_and_the_date(monkeypatch):
    monkeypatch.setattr(metasearch, "DDGS", FakeDDGS)

    result = metasearch.search_news("meal kits")[0]

    assert result["url"] == "https://n.example"
    assert result["content"] == "The Paper: Story"
    assert result["published_date"] == "2026-11-03"


def test_metasearch_failure_becomes_a_source_error(monkeypatch):
    class BrokenDDGS:
        def text(self, query, max_results, backend):
            raise RuntimeError("rate limited")

    monkeypatch.setattr(metasearch, "DDGS", BrokenDDGS)

    with pytest.raises(SourceError, match="rate limited"):
        metasearch.search("meal kits")


def test_metasearch_moves_to_the_next_engine_when_one_has_no_results(monkeypatch):
    tried = []

    class PatchyDDGS:
        def text(self, query, max_results, backend):
            tried.append(backend)
            if backend == "bing":
                raise RuntimeError("No results found.")
            if backend == "yahoo":
                return []
            return [{"title": "Hit", "href": "https://h.example", "body": "Text"}]

    monkeypatch.setattr(metasearch, "DDGS", PatchyDDGS)

    results = metasearch.search("meal kits")

    assert tried == ["bing", "yahoo", "google"]
    assert results[0]["url"] == "https://h.example"


# --- Wikipedia ----------------------------------------------------------------

def test_wikipedia_search_builds_links_and_removes_highlight_tags(monkeypatch):
    reply = {"query": {"search": [
        {"title": "Meal kit", "snippet": 'A <span class="searchmatch">meal</span> kit is'},
    ]}}
    monkeypatch.setattr(http, "get", lambda url, params=None: FakeResponse(reply))

    assert wikipedia.search("meal kit") == [{
        "title": "Meal kit (Wikipedia)",
        "url": "https://en.wikipedia.org/wiki/Meal_kit",
        "content": "A meal kit is",
    }]


def test_wikipedia_unexpected_reply_becomes_a_source_error(monkeypatch):
    monkeypatch.setattr(http, "get",
                        lambda url, params=None: FakeResponse({"error": "bad"}))

    with pytest.raises(SourceError):
        wikipedia.search("meal kit")


# --- Google News --------------------------------------------------------------

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title>HelloFresh expands in Germany</title>
  <link>https://news.google.com/rss/articles/abc</link>
  <pubDate>Mon, 02 Nov 2026 08:00:00 GMT</pubDate>
  <source url="https://paper.example">The Paper</source>
</item>
</channel></rss>"""


def test_google_news_reads_headline_link_date_and_outlet(monkeypatch):
    monkeypatch.setattr(http, "get",
                        lambda url, params=None: FakeResponse(text=FEED))

    result = google_news.search_news("HelloFresh Germany")[0]

    assert result["title"] == "HelloFresh expands in Germany"
    assert result["url"] == "https://news.google.com/rss/articles/abc"
    assert result["published_date"] == "Mon, 02 Nov 2026 08:00:00 GMT"
    assert result["content"].startswith("The Paper")


def test_google_news_asks_for_the_configured_time_window(monkeypatch):
    seen = {}

    def fake_get(url, params=None):
        seen.update(params)
        return FakeResponse(text=FEED)

    monkeypatch.setattr(http, "get", fake_get)

    google_news.search_news("meal kits")

    assert seen["q"] == "meal kits when:30d"


def test_google_news_with_no_articles_returns_an_empty_list(monkeypatch):
    empty_feed = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    monkeypatch.setattr(http, "get",
                        lambda url, params=None: FakeResponse(text=empty_feed))

    assert google_news.search_news("nothing") == []
