"""Tests for the Wikidata company lookup and the financials fallback, using
fake replies (no internet)."""

import pytest

from agent import tools
from agent.sources import SourceError, wikidata


def dated(amount: str, year: str, unit: str = "1") -> dict:
    """A Wikidata figure with the year it refers to."""
    return {
        "mainsnak": {"datavalue": {"value": {"amount": amount, "unit": unit}}},
        "qualifiers": {"P585": [{"datavalue": {"value": {
            "time": f"+{year}-12-31T00:00:00Z"}}}]},
    }


def plain(value) -> dict:
    return {"mainsnak": {"datavalue": {"value": value}}}


COMPANY_ENTRY = {"claims": {
    "P571": [plain({"time": "+2011-00-00T00:00:00Z"})],
    "P159": [plain({"id": "Q64"})],
    "P17": [plain({"id": "Q183"})],
    "P1128": [dated("+2715", "2017"), dated("+19012", "2023"), dated("+4276", "2018")],
    "P2139": [dated("+7600000000", "2023", unit="http://www.wikidata.org/entity/Q4916")],
    "P856": [plain("https://www.hellofresh.com")],
}}


def fake_wikidata(monkeypatch, search_hits: list, entry: dict | None = None):
    """Answer Wikidata requests from memory."""
    def fake_api(**params):
        if params["action"] == "wbsearchentities":
            return {"search": search_hits}
        if params.get("props") == "labels":
            names = {"Q64": "Berlin", "Q183": "Germany", "Q4916": "euro"}
            return {"entities": {entity_id: {"labels": {"en": {"value": names[entity_id]}}}
                                 for entity_id in params["ids"].split("|")}}
        return {"entities": {params["ids"]: entry or {"claims": {}}}}

    monkeypatch.setattr(wikidata, "_api", fake_api)


# --- choosing the right entry ---------------------------------------------------

def test_find_company_skips_films_and_animals_with_the_same_name(monkeypatch):
    fake_wikidata(monkeypatch, [
        {"id": "Q1", "label": "Gorillas", "description": "1991 video game"},
        {"id": "Q2", "label": "Gorillas", "description": "genus of large African apes"},
        {"id": "Q3", "label": "Gorillas", "description": "grocery delivery company"},
    ])

    assert wikidata.find_company("Gorillas")["id"] == "Q3"


def test_find_company_returns_none_when_nothing_is_a_company(monkeypatch):
    fake_wikidata(monkeypatch, [
        {"id": "Q1", "label": "Apple", "description": "fruit of the apple tree"},
    ])

    assert wikidata.find_company("Apple") is None


def test_latest_picks_the_most_recent_year_whatever_the_order():
    claims = [dated("+2715", "2017"), dated("+19012", "2023"), dated("+4276", "2018")]

    assert wikidata.latest(claims)["mainsnak"]["datavalue"]["value"]["amount"] == "+19012"


# --- the facts ---------------------------------------------------------------------

def test_company_facts_shows_each_figure_with_its_year(monkeypatch):
    fake_wikidata(monkeypatch, [
        {"id": "Q23014836", "label": "HelloFresh SE", "description": "German meal-kit provider"},
    ], COMPANY_ENTRY)

    text = wikidata.company_facts("HelloFresh")

    assert "Company: HelloFresh SE (German meal-kit provider)" in text
    assert "Founded: 2011" in text
    assert "Headquarters: Berlin, Germany" in text
    assert "Employees: 19,012 (2023)" in text
    assert "Revenue: 7.6 billion euro (2023)" in text
    assert "Source: https://www.wikidata.org/wiki/Q23014836" in text


def test_company_facts_says_not_recorded_for_missing_figures(monkeypatch):
    fake_wikidata(monkeypatch, [
        {"id": "Q9", "label": "Small Co", "description": "food company"},
    ], {"claims": {}})

    text = wikidata.company_facts("Small Co")

    assert "Founded: not recorded" in text
    assert "Employees: not recorded" in text
    assert "Revenue: not recorded" in text


def test_company_facts_returns_none_for_an_unknown_company(monkeypatch):
    fake_wikidata(monkeypatch, [])

    assert wikidata.company_facts("Prepmymeal") is None


# --- the financials tool with its backup ---------------------------------------------

def test_tool_uses_wikidata_for_a_company_that_is_not_listed(monkeypatch):
    monkeypatch.setattr(tools, "FINANCIAL_SOURCES", [
        ("Yahoo Finance", lambda company: None),
        ("Wikidata", lambda company: "Company: Gorillas\nFounded: 2020"),
    ])

    result = tools.get_company_financials.invoke({"company": "Gorillas"})

    assert result == ("Source used: Wikidata (not listed on Yahoo Finance)\n"
                      "Company: Gorillas\nFounded: 2020")


def test_tool_uses_wikidata_and_says_so_when_yahoo_is_down(monkeypatch):
    def down(company):
        raise SourceError("timeout")

    monkeypatch.setattr(tools, "FINANCIAL_SOURCES", [
        ("Yahoo Finance", down),
        ("Wikidata", lambda company: "Company: HelloFresh SE"),
    ])

    result = tools.get_company_financials.invoke({"company": "HelloFresh"})

    assert result.startswith("Source used: Wikidata (Yahoo Finance unavailable)")


def test_tool_does_not_call_wikidata_when_yahoo_answers(monkeypatch):
    called = []
    monkeypatch.setattr(tools, "FINANCIAL_SOURCES", [
        ("Yahoo Finance", lambda company: "Company: HelloFresh SE (ticker HFG.DE)"),
        ("Wikidata", lambda company: called.append(company)),
    ])

    result = tools.get_company_financials.invoke({"company": "HelloFresh"})

    assert result.startswith("Source used: Yahoo Finance\n")
    assert called == []


def test_tool_says_not_found_when_neither_source_knows_the_company(monkeypatch):
    monkeypatch.setattr(tools, "FINANCIAL_SOURCES", [
        ("Yahoo Finance", lambda company: None),
        ("Wikidata", lambda company: None),
    ])

    result = tools.get_company_financials.invoke({"company": "Prepmymeal"})

    assert result.startswith("No public figures found for 'Prepmymeal'")


def test_tool_reports_a_failure_when_both_sources_are_down(monkeypatch):
    def down(company):
        raise SourceError("timeout")

    monkeypatch.setattr(tools, "FINANCIAL_SOURCES", [
        ("Yahoo Finance", down), ("Wikidata", down)])

    result = tools.get_company_financials.invoke({"company": "HelloFresh"})

    assert result.startswith("Financial lookup failed")
    assert "Yahoo Finance (timeout)" in result


# --- brand names ------------------------------------------------------------------------

def test_brand_name_removes_legal_forms_and_country_words():
    assert tools.brand_name("HelloFresh Deutschland GmbH & Co. KG") == "HelloFresh"
    assert tools.brand_name("Löwenanteil GmbH") == "Löwenanteil"
    assert tools.brand_name("Marley Spoon Group SE") == "Marley Spoon"
    assert tools.brand_name("HelloFresh") == "HelloFresh"


def test_tool_retries_with_the_brand_name_when_the_legal_name_is_unknown(monkeypatch):
    asked = []

    def source(company):
        asked.append(company)
        return "Company: HelloFresh SE" if company == "HelloFresh" else None

    monkeypatch.setattr(tools, "FINANCIAL_SOURCES", [("Yahoo Finance", source)])

    result = tools.get_company_financials.invoke(
        {"company": "HelloFresh Deutschland GmbH & Co. KG"})

    assert asked == ["HelloFresh Deutschland GmbH & Co. KG", "HelloFresh"]
    assert result == "Source used: Yahoo Finance\nCompany: HelloFresh SE"


def test_tool_does_not_retry_when_the_name_is_already_a_brand_name(monkeypatch):
    asked = []
    monkeypatch.setattr(tools, "FINANCIAL_SOURCES",
                        [("Yahoo Finance", lambda company: asked.append(company))])

    tools.get_company_financials.invoke({"company": "Prepmymeal"})

    assert asked == ["Prepmymeal"]

