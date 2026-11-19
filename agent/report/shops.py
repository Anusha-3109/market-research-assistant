"""The big online shops of each country, for prices of brands that do not
sell on their own website.

Packaged food and drink, cosmetics and many other products are sold through
supermarkets and online shops; the brand's own website shows the products
but no prices. When that happens, the report looks for a price on these
shops instead (agent/report/research.py), and says that it is a shop price.

Only shops that sell online with prices on the product page are listed,
two to five per country. A country that is not listed gets no shop search.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from agent.countries import find_country


@dataclass(frozen=True)
class Shop:
    name: str        # as shown in the report: "Carrefour"
    domain: str      # the shop's web address without "www.": "carrefour.fr"


def _shops(*pairs: tuple[str, str]) -> tuple[Shop, ...]:
    return tuple(Shop(name, domain) for name, domain in pairs)


# By two-letter country code, as find_country() gives it.
SHOPS: dict[str, tuple[Shop, ...]] = {
    "FR": _shops(("Carrefour", "carrefour.fr"), ("Auchan", "auchan.fr"),
                 ("Monoprix", "monoprix.fr"), ("Intermarché", "intermarche.com"),
                 ("Amazon.fr", "amazon.fr")),
    "DE": _shops(("REWE", "rewe.de"), ("dm", "dm.de"), ("Rossmann", "rossmann.de"),
                 ("Kaufland", "kaufland.de"), ("Amazon.de", "amazon.de")),
    "AT": _shops(("BILLA", "billa.at"), ("dm", "dm.at"), ("Amazon.de", "amazon.de")),
    "CH": _shops(("Coop", "coop.ch"), ("Migros", "migros.ch"), ("Galaxus", "galaxus.ch")),
    "GB": _shops(("Tesco", "tesco.com"), ("Sainsbury's", "sainsburys.co.uk"),
                 ("Ocado", "ocado.com"), ("Asda", "asda.com"), ("Amazon.co.uk", "amazon.co.uk")),
    "IE": _shops(("Tesco", "tesco.ie"), ("SuperValu", "supervalu.ie")),
    "NL": _shops(("Albert Heijn", "ah.nl"), ("Jumbo", "jumbo.com"), ("bol", "bol.com"),
                 ("Amazon.nl", "amazon.nl")),
    "BE": _shops(("Delhaize", "delhaize.be"), ("Colruyt", "colruyt.be"),
                 ("Carrefour", "carrefour.be"), ("bol", "bol.com")),
    "ES": _shops(("Carrefour", "carrefour.es"), ("El Corte Inglés", "elcorteingles.es"),
                 ("Amazon.es", "amazon.es")),
    "IT": _shops(("Carrefour", "carrefour.it"), ("Esselunga", "esselungaacasa.it"),
                 ("Amazon.it", "amazon.it")),
    "PT": _shops(("Continente", "continente.pt"), ("Auchan", "auchan.pt"),
                 ("Pingo Doce", "pingodoce.pt")),
    "PL": _shops(("Carrefour", "carrefour.pl"), ("Frisco", "frisco.pl"),
                 ("Allegro", "allegro.pl"), ("Amazon.pl", "amazon.pl")),
    "SE": _shops(("ICA", "ica.se"), ("Coop", "coop.se"), ("Willys", "willys.se"),
                 ("Amazon.se", "amazon.se")),
    "DK": _shops(("Nemlig", "nemlig.com"), ("Coop", "coop.dk")),
    "NO": _shops(("Oda", "oda.com"), ("Meny", "meny.no")),
    "US": _shops(("Walmart", "walmart.com"), ("Target", "target.com"),
                 ("Amazon.com", "amazon.com")),
    "CA": _shops(("Walmart", "walmart.ca"), ("Loblaws", "loblaws.ca"), ("Amazon.ca", "amazon.ca")),
    "AU": _shops(("Woolworths", "woolworths.com.au"), ("Coles", "coles.com.au"),
                 ("Amazon.com.au", "amazon.com.au")),
}


def shops_for(country: str) -> tuple[Shop, ...]:
    """The shops of a country, by its name (English or German) or code;
    none for a country that is not listed or not a single country."""
    found = find_country(country) if country else None
    return SHOPS.get(found.alpha_2, ()) if found else ()


def shop_of(url: str, shops: tuple[Shop, ...]) -> Shop | None:
    """The shop a web address belongs to, or None. The address's host must
    be the shop's domain or a part of it ("www.carrefour.fr"), so a site
    such as carrefour.fr.example.com is not taken for the shop."""
    host = (urlsplit(url or "").hostname or "").lower()
    if not host:
        return None
    return next((shop for shop in shops
                 if host == shop.domain or host.endswith("." + shop.domain)), None)
