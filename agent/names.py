"""Comparing company names."""

import re
import unicodedata


def name_key(name: str) -> str:
    """Reduce a name to plain lower-case letters and digits, so that
    'Löwenanteil', 'Lowenanteil' and 'LÖWENANTEIL' compare equal."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plain.lower())


def same_company(brand: str, company_name: str) -> bool:
    """True if a full company name is the brand's own name: the brand must
    be the START of the company name, on a word boundary.

    'HelloFresh' matches 'HelloFresh SE' and 'Marley Spoon' matches 'Marley
    Spoon Group SE'. 'Factor' does not match 'The Cheesecake Factory
    Incorporated', and 'Bulk' does not match 'Dry Bulk Carriers Inc'.
    """
    wanted = name_key(brand)
    words = re.findall(r"[^\W_]+", company_name)
    if words and words[0].lower() == "the":
        words = words[1:]
    if not wanted or not words:
        return False
    # Join the first one, two, three ... words and compare, so "Hello Fresh"
    # and "HelloFresh" are treated the same.
    return any(name_key("".join(words[:count])) == wanted
               for count in range(1, len(words) + 1))
