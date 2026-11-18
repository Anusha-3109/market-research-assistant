"""Other layouts of a finished report.

The full report is the text the workflow wrote. The layouts here are put
together by code from the figures kept with the report (its snapshot, see
snapshot.py). No model is asked, so a layout costs nothing and holds
nothing the report did not find; what was not found is said, not left out.
"""

from dataclasses import dataclass, field

from agent.report.snapshot import trend_bars

FULL = "Full market report"
ONE_PAGER = "Investor one-pager"
SLIDES = "Pitch deck slides"

# A line longer than this is cut, so that a slide stays readable.
SLIDE_LINE_MAX_CHARS = 180


def _section(heading: str, lines: list[str]) -> list[str]:
    """A heading with its lines, or nothing if there are no lines."""
    return [f"## {heading}", "", *lines, ""] if lines else []


def one_pager(title: str, snapshot: dict, sources: list) -> str:
    """The report on one page, as markdown: its key figures, the
    competitors, the demand trend, opportunities and risks, and the sources.

    title:   the report's title, such as "Oat milk in Germany".
    sources: the numbered pages the report cites (agent.citations.Source).
    """
    count = len(sources)
    lines = [f"# {title}", "",
             f"Investor one-pager · {count} source" + ("" if count == 1 else "s"), ""]

    figures = []
    for figure in snapshot["figures"]:
        line = f"- {figure['label']}: **{figure['value']}**"
        if figure["note"]:
            line += f" ({figure['note']})"
        if figure.get("converted"):
            line += f"; {figure['converted']}"
        figures.append(line)
    candidates = snapshot["candidates"]
    figures.append(f"- Competitors confirmed: **{snapshot['confirmed']}** of {candidates} "
                   + ("candidate" if candidates == 1 else "candidates"))
    lines += _section("Key figures", figures)

    lines += _section("Competitors", [
        f"- **{row['name']}**: {row['offer'].rstrip('.')}. Size: {row['size'].rstrip('.')}. "
        f"Price: {row['price'].rstrip('.')}."
        for row in snapshot["competitors"]])

    trend = snapshot.get("trend")
    if trend:
        caution = "" if trend["reliable"] else " (few searches, so treat this with caution)"
        lines += _section("Demand", [
            f'- Search interest for "{trend["term"]}": {trend["direction"] or "measured"}{caution}'])

    lines += _section("Opportunities", [f"- {text}" for text in snapshot["opportunities"]])
    # A snapshot saved before risks were kept has no "threats".
    lines += _section("Risks", [f"- {text}" for text in snapshot.get("threats", [])])
    lines += _section("Sources", [f"{source.number}. [{source.title}]({source.url}) ({source.domain})"
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


def slides(title: str, snapshot: dict, sources: list) -> list[Slide]:
    """The report as a handful of slides: the title, the market, the
    competitors, their prices, the demand, opportunities and risks, and the
    sources. A slide that would be empty is left out."""
    count = len(sources)
    deck = [Slide(title, [f"Market research · {count} source" + ("" if count == 1 else "s")])]

    market = []
    for figure in snapshot["figures"]:
        line = f"{figure['label']}: {figure['value']}"
        if figure["note"]:
            line += f" ({figure['note']})"
        if figure.get("converted"):
            line += f"; {figure['converted']}"
        market.append(line)
    candidates = snapshot["candidates"]
    market.append(f"Competitors confirmed: {snapshot['confirmed']} of {candidates} "
                  + ("candidate" if candidates == 1 else "candidates"))
    deck.append(Slide("The market", market))

    competitors = snapshot["competitors"]
    if competitors:
        deck.append(Slide("Competitors", [f"{row['name']}: {row['offer']}" for row in competitors]))
        # What was not found is said, not left out.
        deck.append(Slide("Prices", [f"{row['name']}: {row['price']}" for row in competitors]))

    trend = snapshot.get("trend")
    if trend:
        caution = "" if trend["reliable"] else " (few searches, so treat this with caution)"
        deck.append(Slide(
            "Demand",
            [f'Search interest for "{trend["term"]}": {trend["direction"] or "measured"}{caution}'],
            bars=trend_bars(trend["points"])))

    outlook = ([f"Opportunity: {text}" for text in snapshot["opportunities"]]
               + [f"Risk: {text}" for text in snapshot.get("threats", [])])
    if outlook:
        deck.append(Slide("Opportunities and risks", outlook))

    if sources:
        deck.append(Slide("Sources", [f"{source.number}. {source.title} ({source.domain})"
                                      for source in sources], numbered=True))
    for slide in deck:
        slide.bullets = [_fit(bullet) for bullet in slide.bullets]
    return deck
