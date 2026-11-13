"""Check a finished report against the rules it is supposed to follow.

The language model is asked to follow the report format, but it does not
always do so. This check is plain code: it reads the report text and lists
what is missing. It never changes the report.
"""

import re

SECTIONS = [
    "1. Market overview",
    "2. Competitors",
    "3. Pricing",
    "4. Trends",
    "5. SWOT analysis",
    "6. References",
]
SWOT_LABEL = "assistant's own analysis"
LINK = re.compile(r"https?://\S+")


def split_sections(report: str) -> dict[str, str]:
    """Return the text under each '## ' heading, keyed by the heading."""
    sections: dict[str, str] = {}
    current = None
    for line in report.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = ""
        elif current is not None:
            sections[current] += line + "\n"
    return sections


def bullets(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()
            if line.strip().startswith(("- ", "* "))]


def table_rows(text: str) -> list[list[str]]:
    """Return the data rows of a markdown table as lists of cell texts,
    without the header row and the |---| separator row."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue  # the separator row
        rows.append(cells)
    return rows[1:]  # drop the header


def company_key(name: str) -> str:
    """Reduce a company name to its first word in lower case, so that
    'HelloFresh SE' and 'HelloFresh' count as the same company."""
    words = re.findall(r"\w+", name.lower())
    return words[0] if words else ""


def check_report(report: str) -> list[str]:
    """Return a list of problems found in a report. Empty means it passed."""
    problems = []
    sections = split_sections(report)

    for name in SECTIONS:
        if name not in sections:
            problems.append(f'Section "{name}" is missing')

    # Facts need sources: every bullet in the overview and trends sections.
    for name in ("1. Market overview", "4. Trends"):
        for bullet in bullets(sections.get(name, "")):
            if not LINK.search(bullet):
                problems.append(
                    f'Section "{name}" has a bullet without a source link: '
                    f'"{bullet[:60]}"'
                )

    # Every table row needs a source.
    competitors = table_rows(sections.get("2. Competitors", ""))
    prices = table_rows(sections.get("3. Pricing", ""))
    for name, rows in (("2. Competitors", competitors), ("3. Pricing", prices)):
        if name in sections and not rows:
            problems.append(f'Section "{name}" has no table rows')
        for row in rows:
            if not LINK.search(" ".join(row)):
                problems.append(
                    f'Section "{name}" has a row without a source link: "{row[0]}"'
                )

    # Every competitor must appear in the pricing table.
    priced = {company_key(row[0]) for row in prices}
    for row in competitors:
        if company_key(row[0]) not in priced:
            problems.append(f'Competitor "{row[0]}" has no row in the Pricing table')

    if "5. SWOT analysis" in sections and SWOT_LABEL not in sections["5. SWOT analysis"]:
        problems.append("The SWOT section is not labelled as the assistant's own analysis")

    if "6. References" in sections and not LINK.search(sections["6. References"]):
        problems.append("The References section lists no links")

    return problems


def format_check(problems: list[str]) -> str:
    """Turn the list of problems into a short message for the user."""
    if not problems:
        return "Report check: passed"
    count = f"{len(problems)} issue" + ("s" if len(problems) > 1 else "")
    return "\n".join([f"Report check: {count}"] + [f"- {problem}" for problem in problems])
