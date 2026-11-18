"""A figure in the country's own currency, next to the original.

Market figures are shown exactly as their source wrote them, which is often
in US dollars. For a reader in another country, this module works out the
same amount in the country's own currency, so it can be shown beside the
original. The original is never replaced.

The converted amount is a number no source published. It is therefore
always worded as "about ..., converted at the ECB rate of <date>". It uses
the latest exchange rate, also for a figure about another year, so it is a
rough guide only.

The reading of the amount and the arithmetic are done here, in code, not by
the language model. When a text is not one clear amount, nothing is
converted: no value is better than a wrong one.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date

import requests

from agent.countries import find_country

log = logging.getLogger(__name__)

# The reference rates of the European Central Bank, served by Frankfurter.
# It is free and needs no key. Only the two currency codes are sent.
RATES_URL = "https://api.frankfurter.dev/v1/latest"

EURO_COUNTRIES = {"AT", "BE", "BG", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR", "IE", "IT",
                  "LT", "LU", "LV", "MT", "NL", "PT", "SI", "SK"}
OTHER_COUNTRIES = {
    "GB": "GBP", "US": "USD", "CH": "CHF", "SE": "SEK", "NO": "NOK", "DK": "DKK", "PL": "PLN",
    "CZ": "CZK", "HU": "HUF", "RO": "RON", "IS": "ISK", "TR": "TRY", "CA": "CAD", "MX": "MXN",
    "BR": "BRL", "AU": "AUD", "NZ": "NZD", "JP": "JPY", "CN": "CNY", "KR": "KRW", "IN": "INR",
    "SG": "SGD", "HK": "HKD", "ID": "IDR", "MY": "MYR", "PH": "PHP", "TH": "THB", "IL": "ILS",
    "ZA": "ZAR",
}

# How a currency is written in a figure. Longer forms come first, so that
# "US$" is not read as a plain "$".
CURRENCY_WORDS = [
    (r"US-Dollar|US dollars?|US\$|USD|\$", "USD"),
    (r"Euros?|EUR|€", "EUR"),
    (r"pounds? sterling|GBP|£", "GBP"),
    (r"Swiss francs?|CHF", "CHF"),
    (r"złotych|złoty|zloty|PLN", "PLN"),
    (r"SEK|NOK|DKK|CZK|HUF|RON|CAD|AUD|NZD|JPY|CNY|INR|BRL|MXN|ZAR|TRY|KRW|SGD|HKD", None),
]
SIZES = [
    (r"trillions?|tn", 1e12),
    (r"billions?|bn|Milliarden|Milliarde|Mrd\.?", 1e9),
    (r"millions?|mn|Millionen|Million|Mio\.?", 1e6),
]
NUMBER = re.compile(r"\d[\d.,]*\d|\d")


@dataclass(frozen=True)
class Amount:
    currency: str      # a three-letter code, such as "USD"
    value: float       # the full amount: 1.31 billion is 1310000000


def currency_of(country: str) -> str | None:
    """The currency used in a country, or None if it is not in the table."""
    found = find_country(country)
    if found is None:
        return None
    if found.alpha_2 in EURO_COUNTRIES:
        return "EUR"
    return OTHER_COUNTRIES.get(found.alpha_2)


def _number(text: str) -> float:
    """A number as written in English or in German: "1.31", "1,193",
    "0,3" and "1.234,5" are all read correctly."""
    if "." in text and "," in text:
        decimal = "," if text.rfind(",") > text.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        return float(text.replace(thousands, "").replace(decimal, "."))
    if "," in text:
        whole, _, rest = text.rpartition(",")
        # "1,193" is a thousands comma; "0,3" and "25,1" are decimal commas.
        return float(text.replace(",", "")) if len(rest) == 3 and whole != "0" \
            else float(text.replace(",", "."))
    return float(text)


def read_amount(text: str) -> Amount | None:
    """The one amount of money a figure's text states, or None.

    The text must hold exactly one currency and exactly one number.
    Anything else (a percentage, a range, a text with years in it) is left
    alone, because it cannot be read with confidence.
    """
    currencies = []
    rest = text
    for pattern, code in CURRENCY_WORDS:
        for match in re.finditer(pattern, rest, flags=re.IGNORECASE):
            currencies.append(code or match.group(0).upper())
        rest = re.sub(pattern, " ", rest, flags=re.IGNORECASE)
    numbers = NUMBER.findall(rest)
    if len(currencies) != 1 or len(numbers) != 1 or "%" in text:
        return None

    size = 1.0
    for pattern, factor in SIZES:
        if re.search(rf"(?<![A-Za-z])(?:{pattern})(?![A-Za-z])", rest, flags=re.IGNORECASE):
            size = factor
            break
    try:
        return Amount(currencies[0], _number(numbers[0]) * size)
    except ValueError:
        return None


def format_amount(amount: Amount) -> str:
    """An amount in words a person reads easily: "EUR 279 million". It is
    rounded to three digits that mean something, since a converted amount
    is approximate anyway."""
    value = amount.value
    for name, factor in (("trillion", 1e12), ("billion", 1e9), ("million", 1e6)):
        if value >= factor:
            return f"{amount.currency} {float(f'{value / factor:.3g}'):g} {name}"
    if value >= 1000:
        return f"{amount.currency} {float(f'{value:.3g}'):,.0f}"
    return f"{amount.currency} {value:.2f}"


def real_rate(source: str, target: str) -> tuple[float, str] | None:
    """Today's exchange rate from one currency to another, with its date,
    or None if the service does not have it."""
    response = requests.get(RATES_URL, params={"base": source, "symbols": target}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    rate = (payload.get("rates") or {}).get(target)
    return (float(rate), payload.get("date", "")) if rate else None


def _readable(day: str) -> str:
    """"2026-11-18" as "18 Nov 2026"."""
    try:
        return f"{date.fromisoformat(day):%d %b %Y}".lstrip("0")
    except ValueError:
        return day


def converted_note(value_text: str, country: str, get_rate=None) -> str:
    """What to show beside a figure: its amount in the country's own
    currency, marked as converted. "" if there is nothing to convert, or if
    it cannot be done with confidence.

    A failure of the rate service must never stop a report, so it is
    logged and gives no note.
    """
    amount = read_amount(value_text)
    target = currency_of(country)
    if amount is None or target is None or amount.currency == target:
        return ""
    try:
        found = (get_rate or real_rate)(amount.currency, target)
    except Exception as problem:
        log.warning("No exchange rate for %s to %s: %s", amount.currency, target,
                    type(problem).__name__)
        return ""
    if not found:
        return ""
    rate, day = found
    converted = format_amount(Amount(target, amount.value * rate))
    return f"about {converted}, converted at the ECB rate of {_readable(day)}"
