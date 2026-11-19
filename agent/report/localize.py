"""A finished report in another language.

A report is saved as it was written: with English headings, table heads
and fixed sentences (agent/report/render.py). Other code reads that text
(the report check, the list of sources, the Snapshot), so the saved report
is never changed.

To show or download a report in German, its fixed wording is replaced here.
What the research found is left alone: a source's statement, a company's
offer, a point of the SWOT and every number and link stay as they are.
"""

import re

# English wording that render.py writes, and its German.
PHRASES = {
    "de": [
        ("# Market research report: ", "# Marktforschungsbericht: "),
        ("## 1. Market overview", "## 1. Marktüberblick"),
        ("## 2. Competitors", "## 2. Wettbewerber"),
        ("## 3. Pricing", "## 3. Preise"),
        ("## 4. Trends", "## 4. Trends"),
        ("## 5. SWOT analysis", "## 5. SWOT-Analyse"),
        ("## 6. References", "## 6. Quellen"),
        ("| Company | What they offer | Size or financials | Source |",
         "| Unternehmen | Angebot | Größe oder Finanzzahlen | Quelle |"),
        ("| Company | Product or plan | Price | Source | Date found |",
         "| Unternehmen | Produkt oder Tarif | Preis | Quelle | Gefunden am |"),
        ("[source](", "[Quelle]("),
        ("[figures](", "[Zahlen]("),
        ("[company website](", "[Website des Unternehmens]("),
        ("[website](", "[Website]("),
        ("[evidence](", "[Beleg]("),
        ("[checked](", "[geprüft]("),
        ("This section is the assistant's own analysis, based on the facts above.",
         "Dieser Abschnitt ist die eigene Analyse des Assistenten, auf Grundlage der Fakten oben."),
        ("It is written for the business idea described by the user.",
         "Sie ist für die vom Nutzer beschriebene Geschäftsidee geschrieben."),
        ("It is written for a new entrant in this market (no specific idea was described).",
         "Sie ist für einen neuen Anbieter in diesem Markt geschrieben "
         "(es wurde keine bestimmte Idee beschrieben)."),
        ("The analysis could not be produced.", "Die Analyse konnte nicht erstellt werden."),
        ("**Strengths:**", "**Stärken:**"),
        ("**Weaknesses:**", "**Schwächen:**"),
        ("**Opportunities:**", "**Chancen:**"),
        ("**Threats:**", "**Risiken:**"),
        ("No market figures with a checkable source were found.",
         "Es wurden keine Marktzahlen mit prüfbarer Quelle gefunden."),
        ("No direct competitors could be confirmed from the search results.",
         "Aus den Suchergebnissen konnten keine direkten Wettbewerber bestätigt werden."),
        ("No prices: no competitors were confirmed.",
         "Keine Preise: Es wurden keine Wettbewerber bestätigt."),
        ("No recent news or demand data was found for this market.",
         "Für diesen Markt wurden keine aktuellen Nachrichten oder Nachfragedaten gefunden."),
        ("No reliable demand trend was found: no search word specific to this product had "
         "enough searches to measure.",
         "Es wurde kein verlässlicher Nachfragetrend gefunden: Kein für dieses Produkt "
         "spezifisches Suchwort hatte genug Suchanfragen für eine Messung."),
        ("Reliability is low: there are very few searches for this word.",
         "Die Verlässlichkeit ist gering: Für dieses Wort gibt es sehr wenige Suchanfragen."),
        ("No sources.", "Keine Quellen."),
        # Why a price is missing (agent/report/research.py). These come before
        # "not found" is replaced, because one of them contains those words.
        ("the company's own website was not found",
         "die eigene Website des Unternehmens wurde nicht gefunden"),
        ("the company's website could not be read",
         "die Website des Unternehmens konnte nicht gelesen werden"),
        ("no prices are shown on the pages that were read",
         "auf den gelesenen Seiten werden keine Preise gezeigt"),
        # The labels of a company's figures (agent/sources).
        ("Revenue (last 12 months): ", "Umsatz (letzte 12 Monate): "),
        ("Revenue: ", "Umsatz: "),
        ("Market value: ", "Marktwert: "),
        ("Employees: ", "Beschäftigte: "),
        ("Founded: ", "Gegründet: "),
    ],
}

# Short values and the words of a trend's direction.
SMALL = {
    "de": [
        (re.compile(r"\bnot found\b"), "nicht gefunden"),
        (re.compile(r"\bnot recorded\b"), "nicht erfasst"),
        (re.compile(r"from the first to the last quarter of the period"),
         "vom ersten zum letzten Quartal des Zeitraums"),
    ],
}
FIGURE_LABELS = {"de": [("Revenue (last 12 months): ", "Umsatz (letzte 12 Monate): "),
                        ("Revenue: ", "Umsatz: "), ("Market value: ", "Marktwert: "),
                        ("Employees: ", "Beschäftigte: "), ("Founded: ", "Gegründet: ")]}
DIRECTIONS = {"de": {"rising": "steigend", "falling": "fallend", "stable": "stabil"}}

PREPARED = re.compile(r"Prepared on (\S+) from public sources\. "
                      r"Every fact links to the page it came from\.")
TREND = re.compile(r"Search interest for '([^']*)' in (.+?) over the last 12 months: "
                   r"(.*?)\. This measures searches, not sales\.")
WIDER_AREA = re.compile(r"Note: this covers (.+?), not (.+?) alone\.")


def localize_phrase(text: str, language: str) -> str:
    """A short value in the language asked for: "not found", or the
    direction of a trend such as "rising (+32%)". Anything else is
    returned as it is."""
    if language not in SMALL:
        return text
    for english, german in FIGURE_LABELS[language]:
        text = text.replace(english, german)
    for pattern, german in SMALL[language]:
        text = pattern.sub(german, text)
    first, _, rest = text.partition(" ")
    if first in DIRECTIONS[language]:
        text = DIRECTIONS[language][first] + (" " + rest if rest else "")
    return text


def localize(report: str, language: str) -> str:
    """The report with its fixed wording in the language asked for.
    English, and a language the app does not have, give the report back
    unchanged."""
    if language not in PHRASES:
        return report
    for english, german in PHRASES[language]:
        report = report.replace(english, german)
    report = PREPARED.sub(r"Erstellt am \1 aus öffentlichen Quellen. "
                          r"Jede Angabe verlinkt auf die Seite, von der sie stammt.", report)
    report = TREND.sub(
        lambda found: (f'Suchinteresse für "{found[1]}" in {found[2]} in den letzten 12 Monaten: '
                       f"{localize_phrase(found[3], language)}. "
                       f"Dies misst Suchanfragen, nicht Verkäufe."), report)
    report = WIDER_AREA.sub(r"Hinweis: Dies gilt für \1, nicht für \2 allein.", report)
    for pattern, german in SMALL[language][:2]:
        report = pattern.sub(german, report)
    return report
