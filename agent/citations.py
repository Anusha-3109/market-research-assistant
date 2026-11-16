"""Numbered citations and the source list.

The agent writes its sources as links inside the text, like
[source](https://example.com). For display, each link becomes a small
number, [1], and the pages are listed once, in the order they are first
cited, as "Sources". This is the convention of research papers and of most
research tools: the text stays readable and every claim is still one click
from its source.

Nothing here changes the stored answer; it only prepares a view of it.
"""

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from agent.names import name_key

MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
# One search result as the tools print it: "[2] Title" then "URL: address".
RESULT_BLOCK = re.compile(r"^\[\d+\]\s+(.+?)\s*\nURL:\s*(\S+)", re.MULTILINE)

# Link words that say nothing about the page they point to.
GENERIC_LABELS = {"", "source", "sources", "link", "website", "company website",
                  "figures", "checked", "evidence", "here"}
REFERENCES_HEADING = "## 6. References"
TITLE_MAX_CHARS = 70


@dataclass
class Source:
    number: int
    title: str
    domain: str
    url: str
    official: bool = False     # the page belongs to the company being discussed


def domain_of(url: str) -> str:
    """The site a link points to, without 'www.': 'prepmymeal.com'."""
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def titles_in_results(tool_output: str) -> dict[str, str]:
    """Read page titles out of a search tool's output: address -> title."""
    return {url.rstrip("/"): title for title, url in RESULT_BLOCK.findall(tool_output or "")}


def title_from_url(url: str) -> str:
    """A readable name for a page when its real title is not known, built
    from its address: 'prepmymeal.com: collections / mix linie'."""
    parts = urlsplit(url)
    words = [unquote(part).replace("-", " ").replace("_", " ")
             for part in parts.path.split("/") if part and not part.isdigit()]
    words = [re.sub(r"\.(html?|php|aspx?|pdf)$", "", word) for word in words][-2:]
    domain = domain_of(url)
    return f"{domain}: {' / '.join(words)}" if words else domain


def choose_title(url: str, label: str, titles: dict[str, str]) -> str:
    """The best available name for a source: the page's real title, else
    the words the link was written with, else something from the address."""
    title = titles.get(url.rstrip("/"))
    if not title and label.strip().lower() not in GENERIC_LABELS:
        title = label.strip()
    title = title or title_from_url(url)
    if len(title) > TITLE_MAX_CHARS:
        title = title[:TITLE_MAX_CHARS].rstrip() + "…"
    return title


def site_named_in(text: str, url: str) -> bool:
    """True if the text names the site the link points to, which suggests
    the page is the company's own: a question about 'Prepmymeal' and a link
    to prepmymeal.com.

    The site name must be one whole word of the text. Short names are
    ignored, and words are not joined: "market research" must not make
    marketresearch.com look like the company asked about."""
    labels = domain_of(url).split(".")[:-1]          # drop the ending (.com)
    site = max(labels, key=len) if labels else ""
    return len(site) >= 5 and name_key(site) in {name_key(word) for word in text.split()}


def number_citations(text: str, titles: dict[str, str] | None = None,
                     official_domains: set[str] | None = None,
                     subject: str = "") -> tuple[str, list[Source]]:
    """Replace each link in the text with a numbered citation and return
    the new text with the list of sources.

    A page cited several times keeps one number. A link written with
    meaningful words keeps those words in front of its number.

    Args:
        titles: Known page titles, address -> title.
        official_domains: Sites known to belong to the companies discussed.
        subject: The user's question, used to spot a company's own site.
    """
    titles = titles or {}
    official_domains = official_domains or set()
    sources: list[Source] = []
    numbers: dict[str, int] = {}

    def replace(match: re.Match) -> str:
        label, url = match.group(1), match.group(2)
        key = url.rstrip("/")
        if key not in numbers:
            numbers[key] = len(sources) + 1
            domain = domain_of(url)
            sources.append(Source(
                number=numbers[key],
                title=choose_title(url, label, titles),
                domain=domain,
                url=url,
                official=domain in official_domains or site_named_in(subject, url),
            ))
        citation = f"[[{numbers[key]}]]({url})"
        if label.strip().lower() in GENERIC_LABELS:
            return citation
        return f"{label.strip()} {citation}"

    return MARKDOWN_LINK.sub(replace, text or ""), sources


def without_references(report: str) -> str:
    """A report without its last section, the list of links. In the app the
    Sources panel shows them, so the list would only repeat them. The saved
    and downloaded report keeps the section."""
    position = report.find(REFERENCES_HEADING)
    return report[:position].rstrip() + "\n" if position != -1 else report
