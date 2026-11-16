"""Turn the collected facts into the report text.

Sections 1 to 4 and 6 are written by code, not by the language model. Every
table row and bullet is built directly from a checked fact and its source,
so the model cannot drop a source, change a number or add a company. Only
the SWOT (section 5) is written by the model, because it is analysis.
"""

import re
from datetime import date

from agent.report.state import CompetitorProfile, ReportState, Swot
from agent.names import same_company

MAX_PRICE_ROWS_PER_COMPANY = 3
FIGURE_LINES = ("Revenue", "Employees", "Founded", "Market value")
MISSING = ("not found", "not recorded")
LINK = re.compile(r"\]\((https?://[^)\s]+)\)")
SWOT_LABEL = "This section is the assistant's own analysis, based on the facts above."


def cell(text: str) -> str:
    """Make text safe for a table cell: one line, no column separators."""
    return " ".join(str(text).split()).replace("|", "/")


def shorten(text: str, max_words: int = 14) -> str:
    """Cut a description to a few words. The model is asked for at most 10
    but sometimes writes a paragraph."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;.") + "…"


def link(label: str, url: str) -> str:
    return f"[{label}]({url})"


def trusted_figures(profile: CompetitorProfile) -> list[str]:
    """Return the figure lines for a competitor, or nothing if the lookup
    found a different company.

    A brand name that is also a common word (for example "Bulk" or
    "Factor") can match an unrelated listed company. The figures are used
    only when the company name in them starts with the brand name.
    """
    lines = profile.figures.splitlines()
    company_line = next((line for line in lines if line.startswith("Company:")), "")
    # "Company: HelloFresh SE (ticker HFG.DE)" -> "HelloFresh SE"
    company_name = company_line.removeprefix("Company:").split("(")[0]
    if not same_company(profile.name, company_name):
        return []
    return [line for line in lines
            if line.startswith(FIGURE_LINES) and not line.endswith(MISSING)]


def market_section(state: ReportState) -> str:
    figures = state.get("market_figures", [])
    if not figures:
        return "No market figures with a checkable source were found.\n"

    country = state["country"]
    lines = []
    for figure in figures:
        statement = figure.statement[:1].upper() + figure.statement[1:]
        where = f"{figure.area}, {figure.year}"
        # A figure for a wider area says so, so it is not read as the country's.
        note = "" if figure.scope == "country" else f" Note: this covers {figure.area}, not {country} alone."
        lines.append(f"- {statement}: {figure.value} ({where}).{note} "
                     f"{link('source', figure.source_url)}")
    return "\n".join(lines) + "\n"


def competitors_section(state: ReportState, profiles: list[CompetitorProfile]) -> str:
    if not profiles:
        return "No direct competitors could be confirmed from the search results.\n"

    offers = {c.name: c.offer or c.reason for c in state.get("competitors", [])}
    rows = ["| Company | What they offer | Size or financials | Source |",
            "|---|---|---|---|"]
    for profile in profiles:
        figures = trusted_figures(profile)
        if figures:
            size, source = "; ".join(figures), link("figures", profile.figures_source)
        else:
            size = "not found"
            source = link("website", profile.shop_url) if profile.shop_url else \
                link("evidence", next(c.evidence_url for c in state["competitors"]
                                      if c.name == profile.name))
        rows.append(f"| {cell(profile.name)} | {cell(shorten(offers.get(profile.name, '')))} "
                    f"| {cell(size)} | {source} |")
    return "\n".join(rows) + "\n"


def pricing_section(state: ReportState, profiles: list[CompetitorProfile]) -> str:
    if not profiles:
        return "No prices: no competitors were confirmed.\n"

    today = date.today().isoformat()
    rows = ["| Company | Product or plan | Price | Source | Date found |",
            "|---|---|---|---|---|"]
    for profile in profiles:
        if profile.prices:
            for price in profile.prices[:MAX_PRICE_ROWS_PER_COMPANY]:
                rows.append(f"| {cell(profile.name)} | {cell(price.product)} "
                            f"| {cell(price.price)} "
                            f"| {link('company website', profile.price_source)} | {today} |")
        else:
            # Every competitor gets a row, with the reason no price is shown.
            page = profile.shop_url or next(
                c.evidence_url for c in state["competitors"] if c.name == profile.name)
            rows.append(f"| {cell(profile.name)} | not found | not found "
                        f"({cell(profile.price_note)}) | {link('checked', page)} | {today} |")
    return "\n".join(rows) + "\n"


def trend_bullet(state: ReportState) -> str:
    trend = state.get("trend")
    if trend is None:
        return ""

    def line(prefix: str) -> str:
        found = next((l for l in trend.summary.splitlines() if l.startswith(prefix)), "")
        return found.removeprefix(prefix).strip()

    text = (f"- Search interest for '{trend.term}' in {state['country']} over the "
            f"last 12 months: {line('Direction:')}. This measures searches, not sales.")
    if not trend.reliable:
        text += " Reliability is low: there are very few searches for this word."
    return f"{text} {link('source', line('Source:'))}"


def trends_section(state: ReportState) -> str:
    lines = [f"- {item.summary.rstrip('.')}. ({item.date}) {link('source', item.source_url)}"
             for item in state.get("news", [])]
    demand = trend_bullet(state)
    if demand:
        lines.append(demand)
    if not lines:
        return "No recent news or demand data was found for this market.\n"
    if not demand:
        lines.append("")
        lines.append("No reliable demand trend was found: no search word specific "
                     "to this product had enough searches to measure.")
    return "\n".join(lines) + "\n"


def swot_section(swot: Swot | None, idea: str) -> str:
    subject = "the business idea described by the user" if idea else \
        "a new entrant in this market (no specific idea was described)"
    lines = [SWOT_LABEL, f"It is written for {subject}.", ""]
    if swot is None:
        return "\n".join(lines + ["The analysis could not be produced."]) + "\n"

    for title, points in (("Strengths", swot.strengths), ("Weaknesses", swot.weaknesses),
                          ("Opportunities", swot.opportunities), ("Threats", swot.threats)):
        lines.append(f"**{title}:**")
        lines += [f"- {point}" for point in points]
        lines.append("")
    return "\n".join(lines)


def references_section(*sections: str) -> str:
    """Number every link used above, in the order it first appears."""
    urls = list(dict.fromkeys(url for section in sections for url in LINK.findall(section)))
    if not urls:
        return "No sources.\n"
    return "\n".join(f"{number}. {url}" for number, url in enumerate(urls, start=1)) + "\n"


def ordered_profiles(state: ReportState) -> list[CompetitorProfile]:
    """Competitor profiles in the order the competitors were ranked."""
    order = [c.name for c in state.get("competitors", [])]
    known = [p for p in state.get("profiles", []) if p.name in order]
    return sorted(known, key=lambda profile: order.index(profile.name))


def fact_sections(state: ReportState) -> dict[str, str]:
    """Sections 1 to 4, built from the facts. Also used as the material the
    model reads when it writes the SWOT."""
    profiles = ordered_profiles(state)
    return {
        "1. Market overview": market_section(state),
        "2. Competitors": competitors_section(state, profiles),
        "3. Pricing": pricing_section(state, profiles),
        "4. Trends": trends_section(state),
    }


def render_report(state: ReportState) -> str:
    """Build the complete report text."""
    sections = fact_sections(state)
    sections["5. SWOT analysis"] = swot_section(state.get("swot"), state.get("idea", ""))
    sections["6. References"] = references_section(*sections.values())

    parts = [f"# Market research report: {state['product']} in {state['country']}",
             f"Prepared on {date.today().isoformat()} from public sources. "
             f"Every fact links to the page it came from."]
    for heading, body in sections.items():
        parts.append(f"## {heading}\n{body}")
    return "\n\n".join(parts).rstrip() + "\n"
