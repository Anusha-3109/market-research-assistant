"""Tests for the demand trend: country lookup, the trend arithmetic, the two
sources and the tool. No internet is used."""

from datetime import date

import pandas as pd
import pytest

from agent import tools
from agent.countries import find_country
from agent.sources import SourceError, google_trends, http, wikipedia
from agent.trends import TrendSeries, summarise


def series(values: list[float], note: str = "") -> TrendSeries:
    points = [(f"2026-{month:02d}", value) for month, value in enumerate(values, start=1)]
    return TrendSeries(label="Interest in widgets", unit="index",
                       points=points, url="https://t.example", note=note)


# --- country lookup -------------------------------------------------------------

@pytest.mark.parametrize("typed, code", [
    ("Germany", "DE"),
    ("germany", "DE"),
    ("  Germany ", "DE"),
    ("DE", "DE"),
    ("UK", "GB"),
    ("USA", "US"),
    ("South Korea", "KR"),
])
def test_find_country_understands_common_ways_to_write_a_country(typed, code):
    assert find_country(typed).alpha_2 == code


@pytest.mark.parametrize("typed", ["Atlantis", "", "Europe"])
def test_find_country_returns_none_for_something_that_is_not_a_country(typed):
    assert find_country(typed) is None


# --- the arithmetic --------------------------------------------------------------

def test_a_clear_increase_is_called_rising_with_the_percentage():
    text = summarise(series([10, 10, 10, 12, 14, 16, 18, 20, 20, 20, 20, 20]))

    assert "Direction: rising (+100% from the first to the last quarter" in text


def test_a_clear_decrease_is_called_falling():
    text = summarise(series([40, 40, 40, 35, 30, 25, 22, 20, 20, 20, 20, 20]))

    assert "Direction: falling (-50%" in text


def test_a_small_change_is_called_stable():
    text = summarise(series([100, 100, 100, 104, 96, 101, 99, 103, 105, 105, 105, 105]))

    assert "Direction: stable (+5%" in text


def test_a_start_from_zero_does_not_divide_by_zero():
    text = summarise(series([0, 0, 0, 1, 2, 5, 8, 10, 12, 12, 12, 12]))

    assert "rising from almost nothing" in text


def test_the_summary_shows_the_peak_period_source_and_note():
    text = summarise(series([10, 10, 10, 90, 10, 10, 10, 10, 10, 10, 10, 10],
                            note="worldwide only"))

    assert "peak: 90 on 2026-04" in text
    assert "Period: 2026-01 to 2026-12 (12 data points)" in text
    assert "Source: https://t.example" in text
    assert "Note: worldwide only" in text


# --- Google Trends ---------------------------------------------------------------

def fake_trends(monkeypatch, table: pd.DataFrame, seen: dict | None = None):
    class FakeTrendReq:
        def __init__(self, **options):
            pass

        def build_payload(self, terms, timeframe, geo):
            if seen is not None:
                seen.update(terms=terms, geo=geo)

        def interest_over_time(self):
            return table

    monkeypatch.setattr(google_trends, "TrendReq", FakeTrendReq)


def weekly_table(term: str, values: list[int], partial_last: bool = False) -> pd.DataFrame:
    days = pd.date_range("2026-01-04", periods=len(values), freq="W")
    partial = [False] * len(values)
    partial[-1] = partial_last
    return pd.DataFrame({term: values, "isPartial": partial}, index=days)


def test_google_trends_asks_for_the_country_code_and_returns_dated_points(monkeypatch):
    seen = {}
    fake_trends(monkeypatch, weekly_table("Kochbox", [10, 20, 30]), seen)

    result = google_trends.interest("Kochbox", find_country("Germany"))

    assert seen == {"terms": ["Kochbox"], "geo": "DE"}
    assert result.points == [("2026-01-04", 10.0), ("2026-01-11", 20.0), ("2026-01-18", 30.0)]
    assert result.label == "Google search interest for 'Kochbox' in Germany"
    assert "geo=DE" in result.url


def test_google_trends_leaves_out_the_unfinished_week(monkeypatch):
    fake_trends(monkeypatch, weekly_table("Kochbox", [10, 20, 3], partial_last=True))

    result = google_trends.interest("Kochbox", find_country("Germany"))

    assert [value for _, value in result.points] == [10.0, 20.0]


def test_google_trends_with_no_data_is_a_failure(monkeypatch):
    fake_trends(monkeypatch, pd.DataFrame())

    with pytest.raises(SourceError, match="no search data"):
        google_trends.interest("zzzz", find_country("Germany"))


def test_google_trends_with_only_zeros_is_a_failure(monkeypatch):
    fake_trends(monkeypatch, weekly_table("rare thing", [0, 0, 0]))

    with pytest.raises(SourceError, match="not enough searches"):
        google_trends.interest("rare thing", find_country("Germany"))


def test_google_trends_being_blocked_is_a_failure(monkeypatch):
    class Blocked:
        def __init__(self, **options):
            raise RuntimeError("429 Too Many Requests")

    monkeypatch.setattr(google_trends, "TrendReq", Blocked)

    with pytest.raises(SourceError, match="429"):
        google_trends.interest("Kochbox", find_country("Germany"))


# --- Wikipedia pageviews ---------------------------------------------------------

def test_last_12_full_months_stops_before_the_current_month():
    assert wikipedia.last_12_full_months(date(2026, 11, 13)) == ("2025110100", "2026110100")


class FakeJson:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


def test_wikipedia_pageviews_uses_the_best_matching_article(monkeypatch):
    monkeypatch.setattr(wikipedia, "search", lambda term: [
        {"title": "Meal kit (Wikipedia)", "url": "u", "content": "c"}])
    requested = []

    def fake_get(url, params=None):
        requested.append(url)
        return FakeJson({"items": [
            {"timestamp": f"2026{month:02d}0100", "views": 1000 + month}
            for month in range(1, 7)
        ]})

    monkeypatch.setattr(http, "get", fake_get)

    result = wikipedia.pageviews("meal kit")

    assert "/Meal_kit/monthly/" in requested[0]
    assert result.points[0] == ("2026-01", 1001.0)
    assert result.label == "Views of the English Wikipedia article 'Meal kit'"
    assert "not specific to one country" in result.note


def test_wikipedia_pageviews_without_an_article_is_a_failure(monkeypatch):
    monkeypatch.setattr(wikipedia, "search", lambda term: [])

    with pytest.raises(SourceError, match="no matching Wikipedia article"):
        wikipedia.pageviews("zzzz")


# --- the tool ----------------------------------------------------------------------

def test_tool_reports_direction_and_source(monkeypatch):
    monkeypatch.setattr(tools, "TREND_SOURCES", [
        ("FakeTrends", lambda term, country: series([10] * 6 + [20] * 6))])

    result = tools.get_demand_trend.invoke({"term": "Kochbox", "country": "Germany"})

    assert result.startswith("Source used: FakeTrends\nInterest in widgets")
    assert "Direction: rising" in result


def test_tool_passes_the_country_record_to_the_source(monkeypatch):
    seen = {}

    def source(term, country):
        seen.update(term=term, code=country.alpha_2)
        return series([10] * 12)

    monkeypatch.setattr(tools, "TREND_SOURCES", [("FakeTrends", source)])

    tools.get_demand_trend.invoke({"term": "Kochbox", "country": "germany"})

    assert seen == {"term": "Kochbox", "code": "DE"}


def test_tool_uses_the_backup_when_google_trends_is_blocked(monkeypatch):
    def blocked(term, country):
        raise SourceError("429 Too Many Requests")

    monkeypatch.setattr(tools, "TREND_SOURCES", [
        ("Google Trends", blocked),
        ("Wikipedia pageviews", lambda term, country: series([10] * 12))])

    result = tools.get_demand_trend.invoke({"term": "Kochbox", "country": "Germany"})

    assert result.startswith("Source used: Wikipedia pageviews (Google Trends unavailable)")


def test_tool_asks_for_a_real_country_without_calling_any_source(monkeypatch):
    called = []
    monkeypatch.setattr(tools, "TREND_SOURCES", [
        ("FakeTrends", lambda term, country: called.append(term))])

    result = tools.get_demand_trend.invoke({"term": "Kochbox", "country": "Atlantis"})

    assert "was not recognised" in result
    assert called == []


def test_tool_says_not_found_when_no_source_has_data(monkeypatch):
    def empty(term, country):
        raise SourceError("no search data for this term")

    monkeypatch.setattr(tools, "TREND_SOURCES", [("FakeTrends", empty)])

    result = tools.get_demand_trend.invoke({"term": "zzzz", "country": "Germany"})

    assert result.startswith("No trend data found")
    assert "'not found'" in result
