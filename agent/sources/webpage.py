"""Read a web page directly, with our own code. Backup for Tavily Extract.

Security: the address is chosen by the model, and the model reads untrusted
web text, so a malicious page could try to make it open an internal address
(for example a router page or a cloud metadata service). check_url blocks
that. It is applied to the first address and again to every redirect.
"""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from agent.config import PAGE_MAX_BYTES, SOURCE_TIMEOUT_SECONDS
from agent.sources import SourceError
from agent.sources.http import HEADERS

MAX_REDIRECTS = 5
READABLE_TYPES = ("text/html", "text/plain", "application/xhtml+xml")
# Parts of a page that are never the content.
NOISE_TAGS = ["script", "style", "noscript", "svg", "nav", "footer", "form", "iframe"]


class UnsafeUrlError(ValueError):
    """The address is not allowed. The message says why."""


def check_url(url: str) -> None:
    """Raise UnsafeUrlError unless the URL is a public web address."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrlError("only http and https addresses are allowed")
    if not parts.hostname:
        raise UnsafeUrlError("the address has no host name")
    if parts.username or parts.password:
        raise UnsafeUrlError("addresses with a user name or password are not allowed")

    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        resolved = socket.getaddrinfo(parts.hostname, port)
    except (socket.gaierror, ValueError) as error:
        raise UnsafeUrlError(f"the host name could not be found: {parts.hostname}") from error

    # A name can point at several addresses; every one must be public.
    for entry in resolved:
        address = ipaddress.ip_address(entry[4][0])
        if not address.is_global:
            raise UnsafeUrlError("local and private network addresses are not allowed")


def html_to_text(html: str) -> str:
    """Return the readable text of an HTML page, one line per block."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    lines = (line.strip() for line in soup.get_text(separator="\n").splitlines())
    return "\n".join(line for line in lines if line)


def _download(url: str) -> requests.Response:
    """Fetch one address without following redirects, reading at most
    PAGE_MAX_BYTES so a huge file cannot fill the memory."""
    response = requests.get(
        url, headers=HEADERS, timeout=SOURCE_TIMEOUT_SECONDS,
        allow_redirects=False, stream=True,
    )
    if not response.is_redirect:
        response._content = response.raw.read(PAGE_MAX_BYTES, decode_content=True)
    return response


def fetch(url: str) -> str:
    """Download a public web page and return its readable text.

    Raises UnsafeUrlError for a blocked address and SourceError when the
    page cannot be read.
    """
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        try:
            response = _download(url)
        except requests.RequestException as error:
            raise SourceError(str(error)) from error

        if response.is_redirect:
            # Follow redirects ourselves so each new address is checked too.
            url = urljoin(url, response.headers.get("Location", ""))
            continue

        if not response.ok:
            raise SourceError(f"HTTP {response.status_code} from {url}")

        content_type = response.headers.get("Content-Type", "").lower()
        if not content_type.startswith(READABLE_TYPES):
            raise SourceError(f"not a readable page (type: {content_type or 'unknown'})")

        if content_type.startswith("text/plain"):
            return response.text.strip()
        return html_to_text(response.text)

    raise SourceError("too many redirects")
