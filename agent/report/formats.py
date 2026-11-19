"""Other layouts of a finished report.

The full report is the text the workflow wrote. The layouts here are put
together by code from the figures kept with the report (its snapshot, see
snapshot.py). No model is asked, so a layout costs nothing and holds
nothing the report did not find; what was not found is said, not left out.

A layout can be made in English or in German. Only its own wording changes:
what the research found stays as it was kept.
"""

from dataclasses import dataclass, field

from agent.report.localize import localize_phrase
from agent.report.snapshot import trend_bars

FULL = "Full market report"
ONE_PAGER = "Investor one-pager"
SLIDES = "Pitch deck slides"

# A line longer than this is cut, so that a slide stays readable.
SLIDE_LINE_MAX_CHARS = 180

# The layouts' own wording. (one, many) pairs name a number of things.
WORDS = {
    "en": {
        "one_pager": "Investor one-pager", "deck": "Market research",
        "source": ("source", "sources"), "candidate": ("candidate", "candidates"),
        "confirmed": "Competitors confirmed", "of": "of",
        "figures": "Key figures", "competitors": "Competitors", "demand": "Demand",
        "opportunities": "Opportunities", "risks": "Risks", "sources": "Sources",
        "size": "Size", "price": "Price",
        "interest": 'Search interest for "{term}"', "measured": "measured",
        "caution": " (few searches, so treat this with caution)",
        "market": "The market", "prices": "Prices", "outlook": "Opportunities and risks",
        "opportunity": "Opportunity", "risk": "Risk",
    },
    "de": {
        "one_pager": "Investoren-Einseiter", "deck": "Marktforschung",
        "source": ("Quelle", "Quellen"), "candidate": ("Kandidat", "Kandidaten"),
        "confirmed": "Bestätigte Wettbewerber", "of": "von",
        "figures": "Kennzahlen", "competitors": "Wettbewerber", "demand": "Nachfrage",
        "opportunities": "Chancen", "risks": "Risiken", "sources": "Quellen",
        "size": "Größe", "price": "Preis",
        "interest": 'Suchinteresse für "{term}"', "measured": "gemessen",
        "caution": " (wenige Suchanfragen, daher mit Vorsicht zu lesen)",
        "market": "Der Markt", "prices": "Preise", "outlook": "Chancen und Risiken",
        "opportunity": "Chance", "risk": "Risiko",
    },
}


def _words(language: str) -> dict:
    return WORDS.get(language, WORDS["en"])


def _count(words: dict, name: str, count: int) -> str:
    one, many = words[name]
    return f"{count} {one if count == 1 else many}"


def _section(heading: str, lines: list[str]) -> list[str]:
    """A heading with its lines, or nothing if there are no lines."""
    return [f"## {heading}", "", *lines, ""] if lines else []


def _demand(trend: dict, words: dict, language: str) -> str:
    """One line about the search trend."""
    direction = localize_phrase(trend["direction"], language) if trend["direction"] \
        else words["measured"]
    caution = "" if trend["reliable"] else words["caution"]
    return f"{words['interest'].format(term=trend['term'])}: {direction}{caution}"


def one_pager(title: str, snapshot: dict, sources: list, language: str = "en") -> str:
    """The report on one page, as markdown: its key figures, the
    competitors, the demand trend, opportunities and risks, and the sources.

    title:   the report's title, such as "Oat milk in Germany".
    sources: the numbered pages the report cites (agent.citations.Source).
    """
    words = _words(language)
    lines = [f"# {title}", "",
             f"{words['one_pager']} · {_count(words, 'source', len(sources))}", ""]

    figures = []
    for figure in snapshot["figures"]:
        line = f"- {figure['label']}: **{figure['value']}**"
        if figure["note"]:
            line += f" ({figure['note']})"
        if figure.get("converted"):
            line += f"; {figure['converted']}"
        figures.append(line)
    figures.append(f"- {words['confirmed']}: **{snapshot['confirmed']}** {words['of']} "
                   f"{_count(words, 'candidate', snapshot['candidates'])}")
    lines += _section(words["figures"], figures)

    def value(text: str) -> str:
        return localize_phrase(text, language).rstrip(".")

    lines += _section(words["competitors"], [
        f"- **{row['name']}**: {row['offer'].rstrip('.')}. {words['size']}: {value(row['size'])}. "
        f"{words['price']}: {value(row['price'])}."
        for row in snapshot["competitors"]])

    trend = snapshot.get("trend")
    if trend:
        lines += _section(words["demand"], [f"- {_demand(trend, words, language)}"])

    lines += _section(words["opportunities"], [f"- {text}" for text in snapshot["opportunities"]])
    # A snapshot saved before risks were kept has no "threats".
    lines += _section(words["risks"], [f"- {text}" for text in snapshot.get("threats", [])])
    lines += _section(words["sources"],
                      [f"{source.number}. [{source.title}]({source.url}) ({source.domain})"
                       for source in sources])
    return "\n".join(lines).rstrip() + "\n"


# --- the pitch deck -----------------------------------------------------------------------------

@dataclass
class Slide:
    title: str
    bullets: list[str]
    # The bars of a chart, as (label, value), for the slide about demand.
    bars: list[tuple[str, float]] = field(default_factory=list)
    # True when the lines carry their own numbers, so they get no bullet.
    numbered: bool = False


def _fit(line: str) -> str:
    """A line cut to the length a slide can show."""
    line = " ".join(line.split())
    if len(line) <= SLIDE_LINE_MAX_CHARS:
        return line
    return line[:SLIDE_LINE_MAX_CHARS].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def slides(title: str, snapshot: dict, sources: list, language: str = "en") -> list[Slide]:
    """The report as a handful of slides: the title, the market, the
    competitors, their prices, the demand, opportunities and risks, and the
    sources. A slide that would be empty is left out."""
    words = _words(language)
    deck = [Slide(title, [f"{words['deck']} · {_count(words, 'source', len(sources))}"])]

    market = []
    for figure in snapshot["figures"]:
        line = f"{figure['label']}: {figure['value']}"
        if figure["note"]:
            line += f" ({figure['note']})"
        if figure.get("converted"):
            line += f"; {figure['converted']}"
        market.append(line)
    market.append(f"{words['confirmed']}: {snapshot['confirmed']} {words['of']} "
                  f"{_count(words, 'candidate', snapshot['candidates'])}")
    deck.append(Slide(words["market"], market))

    competitors = snapshot["competitors"]
    if competitors:
        deck.append(Slide(words["competitors"],
                          [f"{row['name']}: {row['offer']}" for row in competitors]))
        # What was not found is said, not left out.
        deck.append(Slide(words["prices"],
                          [f"{row['name']}: {localize_phrase(row['price'], language)}"
                           for row in competitors]))

    trend = snapshot.get("trend")
    if trend:
        deck.append(Slide(words["demand"], [_demand(trend, words, language)],
                          bars=trend_bars(trend["points"])))

    outlook = ([f"{words['opportunity']}: {text}" for text in snapshot["opportunities"]]
               + [f"{words['risk']}: {text}" for text in snapshot.get("threats", [])])
    if outlook:
        deck.append(Slide(words["outlook"], outlook))

    if sources:
        deck.append(Slide(words["sources"], [f"{source.number}. {source.title} ({source.domain})"
                                             for source in sources], numbered=True))
    for slide in deck:
        slide.bullets = [_fit(bullet) for bullet in slide.bullets]
    return deck
