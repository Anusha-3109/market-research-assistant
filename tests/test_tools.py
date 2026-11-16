"""Tests for the agent's tools.

None of these tests use the internet: the outside services are replaced
with small fakes, so the tests are free, fast and repeatable.

Run with:  pytest
"""

from datetime import date

from langchain_core.messages import AIMessage, HumanMessage

from agent import tools
from agent.formatting import format_money
from agent.sources import tavily, yahoo


# --- formatting search results ---------------------------------------------

def test_format_results_numbers_each_result_with_its_url():
    results = [
        {"title": "First", "url": "https://a.example", "content": "Alpha"},
        {"title": "Second", "url": "https://b.example", "content": "Beta"},
    ]

    text = tools.format_results(results)

    assert "[1] First" in text
    assert "URL: https://a.example" in text
    assert "[2] Second" in text


def test_format_results_shows_the_date_for_news():
    results = [{"title": "News", "url": "https://n.example",
                "content": "Story", "published_date": "2026-11-01"}]

    assert "Published: 2026-11-01" in tools.format_results(results)


def test_format_results_handles_no_results():
    assert "No results found" in tools.format_results([])


def test_format_results_shortens_very_long_extracts():
    results = [{"title": "Long", "url": "https://l.example",
                "content": "word " * 5000}]

    assert len(tools.format_results(results)) < 2000


# --- search failures ---------------------------------------------------------

def test_search_failure_returns_a_message_instead_of_crashing(monkeypatch):
    class BrokenSearch:
        def __init__(self, **options):
            pass

        def invoke(self, request):
            raise ConnectionError("no internet")

    monkeypatch.setattr(tavily, "TavilySearch", BrokenSearch)
    # Only Tavily in the list, so the test never reaches a real backup.
    monkeypatch.setattr(tools, "WEB_SEARCH_SOURCES", [("Tavily", tavily.search)])

    result = tools.web_search.invoke({"query": "anything"})

    assert result.startswith("Search failed")
    assert "Tavily (no internet)" in result


def test_search_result_starts_with_the_source_that_answered(monkeypatch):
    def fake_search(query):
        return [{"title": "Hit", "url": "https://h.example", "content": "Text"}]

    monkeypatch.setattr(tools, "WEB_SEARCH_SOURCES", [("FakeSearch", fake_search)])

    result = tools.web_search.invoke({"query": "anything"})

    assert result.startswith("Source used: FakeSearch")
    assert "[1] Hit" in result


def test_search_uses_the_backup_and_says_so_when_the_first_source_is_down(monkeypatch):
    def down(query):
        raise ConnectionError("outage")

    def backup(query):
        return [{"title": "Hit", "url": "https://h.example", "content": "Text"}]

    monkeypatch.setattr(tools, "WEB_SEARCH_SOURCES",
                        [("Primary", down), ("Backup", backup)])

    result = tools.web_search.invoke({"query": "anything"})

    assert result.startswith("Source used: Backup (Primary unavailable)")
    assert "[1] Hit" in result


# --- saving reports ----------------------------------------------------------

def test_safe_filename_cannot_escape_the_reports_folder():
    name = tools.safe_filename("../../secret/passwords")

    assert "/" not in name
    assert "\\" not in name
    assert ".." not in name


def test_safe_filename_starts_with_today_and_ends_with_md():
    name = tools.safe_filename("Healthy Meal Delivery: Germany!")

    assert name == f"{date.today().isoformat()}-healthy-meal-delivery-germany.md"


def test_safe_filename_has_a_fallback_for_an_empty_title():
    assert tools.safe_filename("???").endswith("-report.md")


def test_write_report_creates_the_file_with_the_content(tmp_path):
    path = tools.write_report("My report", "# Hello", tmp_path / "reports")

    assert path.parent == tmp_path / "reports"
    assert path.read_text(encoding="utf-8") == "# Hello"


def test_find_last_report_returns_the_newest_report_from_its_heading():
    messages = [
        AIMessage("# Market research report: old\nOld text"),
        HumanMessage("Make it shorter"),
        AIMessage("Here it is.\n\n# Market research report: new\nPrice: €5 at Löwenanteil"),
        HumanMessage("Save this report."),
    ]

    report = tools.find_last_report(messages)

    assert report == "# Market research report: new\nPrice: €5 at Löwenanteil"


def test_find_last_report_ignores_text_typed_by_the_user():
    messages = [HumanMessage("# Market research report: fake")]

    assert tools.find_last_report(messages) is None


def test_saving_copies_the_report_exactly_including_special_characters(tmp_path):
    messages = [AIMessage("# Market research report: test\nPrice: €5 at Löwenanteil")]

    result = tools.save_latest_report("Test", messages, tmp_path)

    saved = next(tmp_path.iterdir()).read_text(encoding="utf-8")
    assert result.startswith("Report saved to reports/")
    assert saved == "# Market research report: test\nPrice: €5 at Löwenanteil"


def test_saving_without_a_report_saves_nothing(tmp_path):
    messages = [HumanMessage("Save this report."), AIMessage("Which report?")]

    result = tools.save_latest_report("Test", messages, tmp_path)

    assert "Nothing was saved" in result
    assert list(tmp_path.iterdir()) == []


# --- company financials ------------------------------------------------------

def test_format_money_uses_readable_units():
    assert format_money(6_200_000_000, "EUR") == "6.2 billion EUR"
    assert format_money(430_100_000, "EUR") == "430.1 million EUR"
    assert format_money(None, "EUR") == "not found"


def test_private_company_is_reported_as_not_found(monkeypatch):
    class EmptySearch:
        def __init__(self, name, max_results=5):
            self.quotes = []

    monkeypatch.setattr(yahoo.yf, "Search", EmptySearch)

    monkeypatch.setattr(tools, "FINANCIAL_SOURCES",
                        [("Yahoo Finance", yahoo.company_financials)])
    result = tools.get_company_financials.invoke({"company": "Tiny Private Ltd"})

    assert "No public figures found for 'Tiny Private Ltd'" in result
    assert "'not found'" in result


def test_listed_company_returns_figures_and_a_source(monkeypatch):
    class OneShare:
        def __init__(self, name, max_results=5):
            self.quotes = [{"symbol": "HFG.DE", "quoteType": "EQUITY"}]

    class FakeTicker:
        def __init__(self, symbol):
            self.info = {"longName": "HelloFresh SE", "currency": "EUR",
                         "totalRevenue": 6_200_000_000, "sector": "Consumer"}

    monkeypatch.setattr(yahoo.yf, "Search", OneShare)
    monkeypatch.setattr(yahoo.yf, "Ticker", FakeTicker)

    monkeypatch.setattr(tools, "FINANCIAL_SOURCES",
                        [("Yahoo Finance", yahoo.company_financials)])
    result = tools.get_company_financials.invoke({"company": "HelloFresh"})

    assert "HelloFresh SE (ticker HFG.DE)" in result
    assert "6.2 billion EUR" in result
    assert "https://finance.yahoo.com/quote/HFG.DE" in result


def test_a_listed_company_with_a_similar_name_is_not_returned(monkeypatch):
    # Searching "Factor" on Yahoo finds The Cheesecake Factory.
    class WrongCompany:
        def __init__(self, name, max_results=5):
            self.quotes = [{"symbol": "CAKE", "quoteType": "EQUITY",
                            "shortname": "Cheesecake Factory Incorporated"}]

    monkeypatch.setattr(yahoo.yf, "Search", WrongCompany)

    assert yahoo.company_financials("Factor") is None


def test_the_right_company_is_found_behind_a_wrong_first_result(monkeypatch):
    class TwoShares:
        def __init__(self, name, max_results=5):
            self.quotes = [
                {"symbol": "MS1.DU", "quoteType": "EQUITY", "shortname": "468 SPAC II SE"},
                {"symbol": "MS1.DE", "quoteType": "EQUITY", "shortname": "Marley Spoon Group SE"},
            ]

    class FakeTicker:
        def __init__(self, symbol):
            self.info = {"longName": "Marley Spoon Group SE", "currency": "EUR",
                         "totalRevenue": 205_000_000}

    monkeypatch.setattr(yahoo.yf, "Search", TwoShares)
    monkeypatch.setattr(yahoo.yf, "Ticker", FakeTicker)

    result = yahoo.company_financials("Marley Spoon")

    assert "Marley Spoon Group SE (ticker MS1.DE)" in result
    assert "205.0 million EUR" in result


def test_financial_lookup_failure_returns_a_message(monkeypatch):
    def broken(name, max_results=5):
        raise TimeoutError("yahoo is slow")

    monkeypatch.setattr(yahoo.yf, "Search", broken)

    monkeypatch.setattr(tools, "FINANCIAL_SOURCES",
                        [("Yahoo Finance", yahoo.company_financials)])
    result = tools.get_company_financials.invoke({"company": "Anything"})

    assert result.startswith("Financial lookup failed")
