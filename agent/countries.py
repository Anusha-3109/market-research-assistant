"""Turn a country name typed by a person or the model into a standard
country record, so every source can ask for the code it needs."""

import pycountry

# Everyday names that the standard list does not know.
ALIASES = {
    "uk": "GB",
    "u.k.": "GB",
    "great britain": "GB",
    "britain": "GB",
    "england": "GB",
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "america": "US",
    "south korea": "KR",
    "russia": "RU",
    "uae": "AE",
    "turkey": "TR",
    "czech republic": "CZ",
    "holland": "NL",
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
