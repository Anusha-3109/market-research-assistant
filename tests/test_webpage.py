"""Tests for the page reader and its safety check (no internet).

Host names are resolved by a fake, so the tests decide which address a name
points to.
"""

import socket

import pytest
import requests

from agent import tools
from agent.sources import SourceError, webpage

PUBLIC_IP = "93.184.216.34"


def point_hosts_at(monkeypatch, addresses: dict):
    """Make each host name resolve to the given IP address."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host not in addresses:
            raise socket.gaierror("unknown host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addresses[host], port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


class FakeRaw:
    def __init__(self, body: bytes):
        self.body = body

    def read(self, amount, decode_content=True):
        return self.body[:amount]


def fake_page(body="", status=200, content_type="text/html", location=None):
    """Build a web response without using the network."""
    response = requests.Response()
    response.status_code = status
    response.headers["Content-Type"] = content_type
    if location:
        response.headers["Location"] = location
    response.raw = FakeRaw(body.encode("utf-8"))
    response.encoding = "utf-8"
    return response


def serve(monkeypatch, pages: dict):
    """Answer requests.get from a dict of url -> response, and record calls."""
    requested = []

    def fake_get(url, **kwargs):
        requested.append(url)
        return pages[url]

    monkeypatch.setattr(requests, "get", fake_get)
    return requested


# --- the safety check ---------------------------------------------------------

def test_a_public_https_address_is_allowed(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})

    webpage.check_url("https://shop.example/pricing")  # no error


@pytest.mark.parametrize("url", [
    "file:///C:/Users/me/secrets.txt",
    "ftp://shop.example/file",
    "javascript:alert(1)",
])
def test_addresses_that_are_not_web_pages_are_blocked(url):
    with pytest.raises(webpage.UnsafeUrlError, match="only http and https"):
        webpage.check_url(url)


@pytest.mark.parametrize("address", [
    "127.0.0.1",        # this computer
    "10.0.0.5",         # private network
    "192.168.1.1",      # home router
    "169.254.169.254",  # cloud metadata service
])
def test_local_and_private_addresses_are_blocked(monkeypatch, address):
    point_hosts_at(monkeypatch, {address: address})

    with pytest.raises(webpage.UnsafeUrlError, match="local and private"):
        webpage.check_url(f"http://{address}/admin")


def test_a_public_looking_name_that_points_inside_is_blocked(monkeypatch):
    point_hosts_at(monkeypatch, {"innocent.example": "127.0.0.1"})

    with pytest.raises(webpage.UnsafeUrlError, match="local and private"):
        webpage.check_url("http://innocent.example/")


def test_an_address_with_a_password_is_blocked(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})

    with pytest.raises(webpage.UnsafeUrlError, match="user name or password"):
        webpage.check_url("https://admin:secret@shop.example/")


def test_an_unknown_host_is_blocked(monkeypatch):
    point_hosts_at(monkeypatch, {})

    with pytest.raises(webpage.UnsafeUrlError, match="could not be found"):
        webpage.check_url("https://does-not-exist.example/")


# --- turning a page into text -------------------------------------------------

def test_html_to_text_keeps_content_and_drops_scripts_and_menus():
    html = """<html><head><style>p {color: red}</style></head><body>
        <nav>Home | Shop | Login</nav>
        <h1>Pricing</h1>
        <p>Starter box: €39.99 per week</p>
        <script>trackVisitor()</script>
        <footer>Imprint</footer>
    </body></html>"""

    text = webpage.html_to_text(html)

    assert text == "Pricing\nStarter box: €39.99 per week"


# --- fetching -------------------------------------------------------------------

def test_fetch_returns_the_text_of_a_page(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})
    serve(monkeypatch, {
        "https://shop.example/pricing": fake_page("<p>Box: €39.99</p>"),
    })

    assert webpage.fetch("https://shop.example/pricing") == "Box: €39.99"


def test_fetch_follows_a_redirect_to_another_public_page(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})
    requested = serve(monkeypatch, {
        "https://shop.example/old": fake_page(status=301, location="/new"),
        "https://shop.example/new": fake_page("<p>New page</p>"),
    })

    assert webpage.fetch("https://shop.example/old") == "New page"
    assert requested == ["https://shop.example/old", "https://shop.example/new"]


def test_fetch_refuses_a_redirect_into_the_local_network(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP, "192.168.1.1": "192.168.1.1"})
    requested = serve(monkeypatch, {
        "https://shop.example/": fake_page(status=302, location="http://192.168.1.1/admin"),
    })

    with pytest.raises(webpage.UnsafeUrlError):
        webpage.fetch("https://shop.example/")
    assert requested == ["https://shop.example/"]  # the internal page was never requested


def test_fetch_rejects_files_that_are_not_pages(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})
    serve(monkeypatch, {
        "https://shop.example/brochure.pdf": fake_page("%PDF", content_type="application/pdf"),
    })

    with pytest.raises(SourceError, match="not a readable page"):
        webpage.fetch("https://shop.example/brochure.pdf")


def test_fetch_reports_a_missing_page(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})
    serve(monkeypatch, {"https://shop.example/gone": fake_page(status=404)})

    with pytest.raises(SourceError, match="HTTP 404"):
        webpage.fetch("https://shop.example/gone")


def test_fetch_stops_downloading_at_the_size_limit(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})
    monkeypatch.setattr(webpage, "PAGE_MAX_BYTES", 20)
    serve(monkeypatch, {"https://shop.example/big": fake_page("a" * 1000, content_type="text/plain")})

    assert webpage.fetch("https://shop.example/big") == "a" * 20


# --- the read_webpage tool ------------------------------------------------------

def test_tool_refuses_a_blocked_address_without_calling_any_source(monkeypatch):
    called = []
    monkeypatch.setattr(tools, "PAGE_SOURCES",
                        [("Reader", lambda url: called.append(url) or "text")])
    point_hosts_at(monkeypatch, {"127.0.0.1": "127.0.0.1"})

    result = tools.read_webpage.invoke({"url": "http://127.0.0.1:8501/"})

    assert result.startswith("This page cannot be opened")
    assert called == []


def test_tool_uses_the_backup_reader_and_names_it(monkeypatch):
    def down(url):
        raise SourceError("outage")

    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})
    monkeypatch.setattr(tools, "PAGE_SOURCES",
                        [("Primary reader", down), ("Backup reader", lambda url: "Box: €39.99")])

    result = tools.read_webpage.invoke({"url": "https://shop.example/pricing"})

    assert result == ("Source used: Backup reader (Primary reader unavailable)\n"
                      "URL: https://shop.example/pricing\n\nBox: €39.99")


def test_tool_shortens_a_very_long_page_and_says_so(monkeypatch):
    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})
    monkeypatch.setattr(tools, "PAGE_MAX_CHARS", 10)
    monkeypatch.setattr(tools, "PAGE_SOURCES", [("Reader", lambda url: "x" * 500)])

    result = tools.read_webpage.invoke({"url": "https://shop.example/"})

    assert "(page shortened)" in result
    assert result.endswith("\n\n" + "x" * 10)


def test_tool_gives_a_readable_message_when_no_reader_works(monkeypatch):
    def down(url):
        raise SourceError("outage")

    point_hosts_at(monkeypatch, {"shop.example": PUBLIC_IP})
    monkeypatch.setattr(tools, "PAGE_SOURCES", [("Reader", down)])

    result = tools.read_webpage.invoke({"url": "https://shop.example/"})

    assert result.startswith("The page could not be read")
    assert "Reader (outage)" in result
