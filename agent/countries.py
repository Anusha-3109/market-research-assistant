"""Turn a country name typed by a person or the model into a standard
country record, so every source can ask for the code it needs."""

import re

import pycountry

# Everyday names and adjectives that the standard list does not know.
ALIASES = {
    "uk": "GB",
    "u.k.": "GB",
    "great britain": "GB",
    "britain": "GB",
    "british": "GB",
    "england": "GB",
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "america": "US",
    "american": "US",
    "south korea": "KR",
    "russia": "RU",
    "uae": "AE",
    "turkey": "TR",
    "turkish": "TR",
    "czech republic": "CZ",
    "holland": "NL",
    "dutch": "NL",
    "deutschland": "DE",
    "german": "DE",
    "french": "FR",
    "spanish": "ES",
    "italian": "IT",
    "swiss": "CH",
    "polish": "PL",
    "swedish": "SE",
    "danish": "DK",
    "norwegian": "NO",
    "finnish": "FI",
    "irish": "IE",
    "greek": "GR",
    "chinese": "CN",
}


def find_country(name: str):
    """Return the country for a name or code, or None if it is not known.

    The result has .name ("Germany"), .alpha_2 ("DE") and .alpha_3 ("DEU").
    """
    cleaned = (name or "").strip()
    if not cleaned:
        return None

    cleaned = ALIASES.get(cleaned.lower(), cleaned)
    try:
        return pycountry.countries.lookup(cleaned)
    except LookupError:
        return None


def country_names(country) -> set[str]:
    """The names and everyday aliases of a country, in lower case."""
    names = {country.name, getattr(country, "official_name", ""),
             getattr(country, "common_name", "")}
    names |= {alias for alias, code in ALIASES.items() if code == country.alpha_2}
    return {name.lower() for name in names if name}


def is_mentioned(country, text: str) -> bool:
    """True if the text names the country.

    - Names and aliases are matched as whole words, in any letter case
      ("germany", "German", "Deutschland").
    - The two- and three-letter codes count only in capitals ("US", "DE"),
      because "us" and "de" are ordinary words.
    """
    lowered = text.lower()
    for name in country_names(country):
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", lowered):
            return True
    for code in (country.alpha_2, country.alpha_3):
        if re.search(rf"(?<![A-Za-z]){code}(?![A-Za-z])", text):
            return True
    return False
