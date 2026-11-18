"""The key figures of a finished report, kept as separate values.

A report is one text. To show its figures at a glance (the Snapshot view),
the values behind the text are kept next to it: the market figures, the
competitors with their size and one price, the demand trend, and the
four parts of the SWOT.

Everything here is plain data (text, numbers, lists), so it can be saved
with the conversation. Nothing is worked out or estimated: a value that the
research did not find is reported as "not found".
"""

from agent.currency import converted_note

FIGURES_SHOWN = 4
OPPORTUNITIES_SHOWN = 4
SIZE_MAX_CHARS = 110
BARS_SHOWN = 12
NOT_FOUND = "not found"


def _figures(final: dict) -> list[dict]:
    """Up to four market figures. Figures for the country itself come
    first; figures for a wider area fill in if there are too few.

    A figure in a foreign currency also gets its amount in the country's
    own currency, marked as converted (agent/currency.py). The value itself
    stays as its source wrote it.
    """
    figures = final.get("market_figures") or []
    ordered = ([f for f in figures if f.scope == "country"]
               + [f for f in figures if f.scope != "country"])
    country = final.get("country", "")
    return [{"label": f.statement, "value": f.value,
             "note": ", ".join(part for part in (f.area, f.year) if part),
             "url": f.source_url,
             "converted": converted_note(f.value, country)}
            for f in ordered[:FIGURES_SHOWN]]


def _size(figures_text: str) -> str:
    """A company's figures on one line, shortened."""
    line = "; ".join(part.strip() for part in figures_text.splitlines() if part.strip())
    if not line:
        return NOT_FOUND
    return line if len(line) <= SIZE_MAX_CHARS else line[:SIZE_MAX_CHARS].rstrip() + "…"


def _competitors(final: dict) -> list[dict]:
    profiles = {profile.name: profile for profile in final.get("profiles") or []}
    rows = []
    for competitor in final.get("competitors") or []:
        profile = profiles.get(competitor.name)
        first = profile.prices[0] if profile and profile.prices else None
        rows.append({
            "name": competitor.name,
            "offer": competitor.offer or NOT_FOUND,
            "size": _size(profile.figures) if profile else NOT_FOUND,
            "price": f"{first.price} ({first.product})" if first else NOT_FOUND,
            "site": competitor.shop_url,
        })
    return rows


def _direction(summary: str) -> str:
    """The line of a trend summary that says rising, falling or stable."""
    for line in summary.splitlines():
        if line.startswith("Direction: "):
            return line.removeprefix("Direction: ")
    return ""


def _trend(final: dict) -> dict | None:
    trend = final.get("trend")
    if trend is None:
        return None
    return {"term": trend.term, "direction": _direction(trend.summary),
            "reliable": trend.reliable, "unit": trend.unit,
            "points": [[date, value] for date, value in trend.points]}


def build_snapshot(final: dict) -> dict:
    """The snapshot of a finished report, from the workflow's final state."""
    swot = final.get("swot")
    confirmed = len(final.get("competitors") or [])
    return {
        "product": final.get("product", ""),
        "country": final.get("country", ""),
        "figures": _figures(final),
        "competitors": _competitors(final),
        "confirmed": confirmed,
        # Everyone who was looked at: those kept and those dropped.
        "candidates": confirmed + len(final.get("rejected") or []),
        "trend": _trend(final),
        # The four parts of the SWOT, up to four lines each. A snapshot saved
        # before all four were kept has fewer of these.
        "strengths": list(swot.strengths[:OPPORTUNITIES_SHOWN]) if swot else [],
        "weaknesses": list(swot.weaknesses[:OPPORTUNITIES_SHOWN]) if swot else [],
        "opportunities": list(swot.opportunities[:OPPORTUNITIES_SHOWN]) if swot else [],
        "threats": list(swot.threats[:OPPORTUNITIES_SHOWN]) if swot else [],
    }


def trend_bars(points: list) -> list[tuple[str, float]]:
    """The points of a trend as at most twelve bars. More points are
    averaged in equal groups, each bar named after the first date of its
    group."""
    if len(points) <= BARS_SHOWN:
        return [(date, float(value)) for date, value in points]
    size = -(-len(points) // BARS_SHOWN)             # rounded up
    bars = []
    for start in range(0, len(points), size):
        group = points[start:start + size]
        bars.append((group[0][0], sum(value for _, value in group) / len(group)))
    return bars
