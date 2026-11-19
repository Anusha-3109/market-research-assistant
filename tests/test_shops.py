"""Tests for the list of big online shops per country.

When a brand's own website shows no price, the report looks for one on the
big shops of the country (agent/report/research.py). This list says which
shops those are, and which web addresses belong to them.
"""

from agent.report.shops import SHOPS, Shop, shop_of, shops_for


def test_a_country_is_found_by_its_name_in_english_or_german_or_its_code():
    french = shops_for("France")

    assert Shop("Carrefour", "carrefour.fr") in french
    assert shops_for("Frankreich") == french
    assert shops_for("FR") == french


def test_each_country_has_its_own_shops():
    assert Shop("Tesco", "tesco.com") in shops_for("United Kingdom")
    assert Shop("REWE", "rewe.de") in shops_for("Germany")
    assert Shop("Carrefour", "carrefour.fr") not in shops_for("Germany")


def test_a_country_not_in_the_list_has_no_shops():
    assert shops_for("Kenya") == ()
    assert shops_for("Europe") == ()
    assert shops_for("") == ()


def test_a_shop_page_is_known_by_its_address():
    french = shops_for("France")

    assert shop_of("https://www.carrefour.fr/p/filet-vegetal-umiami-3770016162012", french) \
        == Shop("Carrefour", "carrefour.fr")
    assert shop_of("https://www.amazon.fr/dp/B0ABC", french).name == "Amazon.fr"


def test_an_address_that_only_looks_like_a_shop_is_not_one():
    french = shops_for("France")

    assert shop_of("https://carrefour.fr.example.com/p/1", french) is None   # another site
    assert shop_of("https://notcarrefour.fr/p/1", french) is None
    assert shop_of("https://www.carrefour.es/p/1", french) is None           # another country
    assert shop_of("not an address", french) is None
    assert shop_of("", french) is None


def test_every_entry_is_well_formed():
    for code, shops in SHOPS.items():
        assert len(code) == 2 and code.isupper(), code
        assert 2 <= len(shops) <= 5, code
        for shop in shops:
            assert shop.name and "." in shop.domain and "/" not in shop.domain, shop
            assert shop.domain == shop.domain.lower() and not shop.domain.startswith("www."), shop
