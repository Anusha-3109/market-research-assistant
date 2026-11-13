"""Wikidata: basic facts about a company. Backup for Yahoo Finance. No key.

Wikidata is the structured database behind Wikipedia. Unlike Yahoo Finance
it also covers some private companies, but its figures are entered by
volunteers and can be years old, so every figure is shown with its year.
"""

from agent.formatting import format_money
from agent.sources import SourceError, http

API_URL = "https://www.wikidata.org/w/api.php"

# Wikidata property numbers.
FOUNDED = "P571"
HEADQUARTERS = "P159"
COUNTRY = "P17"
EMPLOYEES = "P1128"
REVENUE = "P2139"
WEBSITE = "P856"
POINT_IN_TIME = "P585"

# A search for a company name also finds films, animals and games. An entry
# is accepted only if its description contains one of these words.
COMPANY_WORDS = (
    "company", "business", "provider", "retailer", "startup", "brand",
    "service", "chain", "corporation", "enterprise", "manufacturer", "firm",
    "supermarket", "restaurant", "platform", "bank", "airline",
)


def _api(**params) -> dict:
    response = http.get(API_URL, params={**params, "format": "json"})
    try:
        return response.json()
    except ValueError as error:
        raise SourceError("unexpected response from Wikidata") from error


def find_company(name: str) -> dict | None:
    """Return the first search hit that is described as a company."""
    hits = _api(action="wbsearchentities", search=name, language="en",
                type="item", limit=5).get("search", [])
    for hit in hits:
        description = (hit.get("description") or "").lower()
        if any(word in description for word in COMPANY_WORDS):
            return hit
    return None


def _value(claim: dict):
    return claim.get("mainsnak", {}).get("datavalue", {}).get("value")


def _year(time_value: dict | None) -> str:
    """'+2018-12-31T00:00:00Z' -> '2018'."""
    return (time_value or {}).get("time", "")[1:5]


def _claim_year(claim: dict) -> str:
    """The year a figure refers to, from its 'point in time' qualifier."""
    qualifiers = claim.get("qualifiers", {}).get(POINT_IN_TIME, [])
    if not qualifiers:
        return ""
    return _year(qualifiers[0].get("datavalue", {}).get("value"))


def latest(claims: list[dict]) -> dict | None:
    """Pick the most recent of several dated figures (for example the
    employee count for each year)."""
    usable = [claim for claim in claims if _value(claim) is not None]
    if not usable:
        return None
    return max(usable, key=_claim_year)


def _labels(ids: list[str]) -> dict[str, str]:
    """Look up the English names of other entries, such as a city."""
    if not ids:
        return {}
    entities = _api(action="wbgetentities", ids="|".join(ids), props="labels",
                    languages="en|mul").get("entities", {})
    names = {}
    for entity_id, entity in entities.items():
        labels = entity.get("labels", {})
        label = labels.get("en") or labels.get("mul") or {}
        names[entity_id] = label.get("value", entity_id)
    return names


def company_facts(name: str) -> str | None:
    """Return founding year, headquarters, employees and revenue for a
    company as text, or None when Wikidata has no matching company."""
    hit = find_company(name)
    if hit is None:
        return None

    entity_id = hit["id"]
    entity = _api(action="wbgetentities", ids=entity_id,
                  props="claims").get("entities", {}).get(entity_id, {})
    claims = entity.get("claims", {})

    def first(prop):
        return _value(claims[prop][0]) if claims.get(prop) else None

    headquarters, country = first(HEADQUARTERS), first(COUNTRY)
    employees, revenue = latest(claims.get(EMPLOYEES, [])), latest(claims.get(REVENUE, []))
    # A revenue figure names its currency as a link to another entry.
    currency_id = (_value(revenue)["unit"].rsplit("/", 1)[-1] if revenue else None)

    wanted = [item["id"] for item in (headquarters, country) if item]
    if currency_id and currency_id.startswith("Q"):
        wanted.append(currency_id)
    names = _labels(wanted)

    place = ", ".join(names[item["id"]] for item in (headquarters, country) if item)

    def dated(text: str, claim: dict) -> str:
        year = _claim_year(claim)
        return f"{text} ({year})" if year else f"{text} (year not recorded)"

    employees_text = (dated(f"{float(_value(employees)['amount']):,.0f}", employees)
                      if employees else "not recorded")
    revenue_text = (dated(format_money(float(_value(revenue)["amount"]),
                                       names.get(currency_id, "")), revenue)
                    if revenue else "not recorded")

    return "\n".join([
        f"Company: {hit.get('label') or name} ({hit.get('description')})",
        f"Founded: {_year(first(FOUNDED)) or 'not recorded'}",
        f"Headquarters: {place or 'not recorded'}",
        f"Employees: {employees_text}",
        f"Revenue: {revenue_text}",
        f"Website: {first(WEBSITE) or 'not recorded'}",
        f"Source: https://www.wikidata.org/wiki/{entity_id}",
        "Wikidata figures are entered by volunteers and can be years old. "
        "Always quote the year shown with a figure. Check that the company "
        "above is the one you meant; if not, report 'not found'.",
    ])
