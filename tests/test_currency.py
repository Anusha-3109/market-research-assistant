"""Tests for showing a figure in the country's own currency as well.

A figure stays exactly as its source wrote it. Next to it, a converted
value may be shown, always marked as converted, with the rate's date. The
exchange rate is a fake one here: no test uses the internet.
"""

import pytest

from agent import currency
from agent.currency import Amount, converted_note, currency_of, format_amount, read_amount

# Kept under a name of its own: the tests' shared settings replace
# agent.currency.real_rate, so that no test reaches the internet.
ask_the_service = currency.real_rate


def rate_of(rates: dict):
    """A stand-in for the exchange-rate service."""
    asked = []

    def get_rate(source: str, target: str):
        asked.append((source, target))
        value = rates.get((source, target))
        return (value, "2026-11-18") if value else None

    get_rate.asked = asked
    return get_rate


# --- reading an amount out of a figure's text ---------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("USD 1.31 Billion", Amount("USD", 1_310_000_000)),
    ("USD 932.18 Million", Amount("USD", 932_180_000)),
    ("$4.40 billion", Amount("USD", 4_400_000_000)),
    ("US$ 2.5 bn", Amount("USD", 2_500_000_000)),
    ("0.3 Milliarden US-Dollar", Amount("USD", 300_000_000)),
    ("0,3 Mrd. US-Dollar", Amount("USD", 300_000_000)),
    ("USD 1,193 Mn", Amount("USD", 1_193_000_000)),
    ("3.5 billion złotych", Amount("PLN", 3_500_000_000)),
    ("EUR 25,1 Mio.", Amount("EUR", 25_100_000)),
    ("€ 1.2 trillion", Amount("EUR", 1_200_000_000_000)),
    ("£450 million", Amount("GBP", 450_000_000)),
    ("5.93 EUR", Amount("EUR", 5.93)),
])
def test_an_amount_with_its_currency_is_read_from_the_text(text, expected):
    assert read_amount(text) == expected


@pytest.mark.parametrize("text", [
    "über 10,2 %",                                   # not money
    "24.4%",
    "50.3 Mn orders",                                # a number without a currency
    "USD 0.48 billion to USD 774.3 million",         # two amounts: which one?
    "USD 289.3 million between 2025 and 2030",       # other numbers in the text
    "more than 2%",
    "",
])
def test_a_text_that_is_not_one_clear_amount_is_left_alone(text):
    assert read_amount(text) is None


# --- the currency of a country --------------------------------------------------------------------

def test_a_countrys_currency_is_known_for_the_common_ones():
    assert [currency_of(country) for country in
            ("Germany", "France", "United Kingdom", "Poland", "United States", "Switzerland")] == \
        ["EUR", "EUR", "GBP", "PLN", "USD", "CHF"]


def test_an_unknown_country_has_no_currency():
    assert currency_of("Atlantis") is None
    assert currency_of("") is None


# --- how a converted amount is written -------------------------------------------------------------

@pytest.mark.parametrize("value, written", [
    (279_000_000, "EUR 279 million"),
    (1_194_600_000, "EUR 1.19 billion"),
    (25_100_000, "EUR 25.1 million"),
    (1_200_000_000_000, "EUR 1.2 trillion"),
    (5.4066, "EUR 5.41"),
    (84_300, "EUR 84,300"),
])
def test_a_converted_amount_is_rounded_to_three_digits_that_mean_something(value, written):
    assert format_amount(Amount("EUR", value)) == written


# --- the note next to a figure ----------------------------------------------------------------------

def test_a_figure_in_another_currency_gets_a_converted_value_marked_as_such():
    note = converted_note("USD 0.3 billion", "Germany", get_rate=rate_of({("USD", "EUR"): 0.93}))

    assert note == "about EUR 279 million, converted at the ECB rate of 18 Nov 2026"


def test_a_figure_already_in_the_countrys_currency_gets_no_note():
    get_rate = rate_of({("EUR", "EUR"): 1.0})

    assert converted_note("EUR 25,1 Mio.", "Germany", get_rate=get_rate) == ""
    assert get_rate.asked == []                      # no rate was even asked for


def test_no_note_without_a_clear_amount_a_known_country_or_a_rate():
    get_rate = rate_of({("USD", "EUR"): 0.93})

    assert converted_note("über 10,2 %", "Germany", get_rate=get_rate) == ""
    assert converted_note("USD 0.3 billion", "Atlantis", get_rate=get_rate) == ""
    assert converted_note("USD 0.3 billion", "Poland", get_rate=get_rate) == ""     # no USD-PLN rate


def test_a_rate_service_that_fails_gives_no_note_and_no_error():
    def broken(source, target):
        raise OSError("the rate service is unreachable")

    assert converted_note("USD 0.3 billion", "Germany", get_rate=broken) == ""


# --- asking the rate service ----------------------------------------------------------------------

class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OSError(f"status {self.status_code}")

    def json(self):
        return self.payload


def test_the_rate_and_its_date_are_read_from_the_services_answer(monkeypatch):
    asked = {}

    def get(url, params=None, timeout=None):
        asked.update(url=url, params=params, timeout=timeout)
        return FakeResponse({"base": "USD", "date": "2026-11-18", "rates": {"EUR": 0.91174}})

    monkeypatch.setattr(currency.requests, "get", get)

    assert ask_the_service("USD", "EUR") == (0.91174, "2026-11-18")
    # Only the two currency codes are sent.
    assert asked["params"] == {"base": "USD", "symbols": "EUR"}
    assert asked["timeout"] is not None


def test_an_answer_without_the_rate_is_no_rate(monkeypatch):
    monkeypatch.setattr(currency.requests, "get",
                        lambda *args, **kwargs: FakeResponse({"rates": {}}))

    assert ask_the_service("USD", "EUR") is None
