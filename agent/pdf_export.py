"""Turn a report into a PDF file.

The report is markdown that this app writes itself, in a small, fixed
subset: one title, section headings, paragraphs, bullet lists, numbered
lists and tables, with **bold** and [links](address). This file converts
exactly that subset; it is not a general markdown converter.

ReportLab's built-in fonts are used so that no font file has to be shipped.
They cover Western European text, including the euro sign and umlauts.
Characters outside that range are replaced with "?".
"""

import re
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#1c1c1a")
MUTED = colors.HexColor("#55544f")
RULE = colors.HexColor("#d9d6cf")
LINK = "#185FA5"

BOLD = re.compile(r"\*\*(.+?)\*\*")
MD_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
BARE_URL = re.compile(r"(?<![\"'>=])\bhttps?://[^\s<)]+")
NUMBERED = re.compile(r"^\d+\.\s+")


def _styles() -> dict:
    base = getSampleStyleSheet()["BodyText"]
    body = ParagraphStyle("body", parent=base, fontName="Helvetica", fontSize=9.5,
                          leading=13.5, textColor=INK, spaceAfter=4)
    return {
        "body": body,
        "title": ParagraphStyle("title", parent=body, fontName="Helvetica-Bold",
                                fontSize=17, leading=21, spaceAfter=6),
        "heading": ParagraphStyle("heading", parent=body, fontName="Helvetica-Bold",
                                  fontSize=12, leading=15, spaceBefore=10, spaceAfter=5),
        "cell": ParagraphStyle("cell", parent=body, fontSize=8, leading=10.5, spaceAfter=0),
        "head": ParagraphStyle("head", parent=body, fontName="Helvetica-Bold",
                               fontSize=8, leading=10.5, spaceAfter=0),
    }


def printable(text: str) -> str:
    """Keep only characters the built-in fonts can draw."""
    return text.encode("cp1252", errors="replace").decode("cp1252")


def inline(text: str) -> str:
    """Convert **bold** and links in one line to ReportLab's own markup.

    The text is escaped first, so any angle brackets that came from a web
    page are shown as text and cannot be read as markup.
    """
    text = escape(printable(text), quote=False)
    text = MD_LINK.sub(
        lambda m: f'<a href="{m.group(2)}" color="{LINK}">{m.group(1) or m.group(2)}</a>', text)
    text = BARE_URL.sub(lambda m: f'<a href="{m.group(0)}" color="{LINK}">{m.group(0)}</a>', text)
    return BOLD.sub(r"<b>\1</b>", text)


def _table(rows: list[list[str]], styles: dict, width: float) -> Table:
    data = [[Paragraph(inline(cell), styles["head" if index == 0 else "cell"])
             for cell in row] for index, row in enumerate(rows)]
    columns = max(len(row) for row in rows)
    table = Table(data, colWidths=[width / columns] * columns, repeatRows=1)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def parse_table_row(line: str) -> list[str] | None:
    """Split one markdown table line into cells. Returns None for the
    |---|---| line that only separates the header."""
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if all(set(cell) <= set("-: ") for cell in cells):
        return None
    return cells


def report_to_pdf(markdown: str) -> bytes:
    """Return the report as the bytes of a PDF file."""
    styles = _styles()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                                 topMargin=16 * mm, bottomMargin=16 * mm,
                                 title="Market research report")
    story = []
    table_rows: list[list[str]] = []
    bullets: list[str] = []
    numbered = False

    def flush() -> None:
        """Write out a table or list that has just ended."""
        nonlocal table_rows, bullets, numbered
        if table_rows:
            story.append(_table(table_rows, styles, document.width))
            story.append(Spacer(1, 6))
            table_rows = []
        if bullets:
            items = [ListItem(Paragraph(inline(item), styles["body"]), leftIndent=12)
                     for item in bullets]
            story.append(ListFlowable(items, bulletType="1" if numbered else "bullet",
                                      start=None if numbered else "•", leftIndent=12,
                                      bulletFontSize=8))
            bullets, numbered = [], False

    for raw in markdown.splitlines():
        line = raw.strip()

        if line.startswith("|"):
            if bullets:
                flush()
            row = parse_table_row(line)
            if row:
                table_rows.append(row)
            continue
        if line.startswith(("- ", "* ")) or NUMBERED.match(line):
            if table_rows:
                flush()
            numbered = bool(NUMBERED.match(line))
            bullets.append(NUMBERED.sub("", line) if numbered else line[2:])
            continue

        flush()
        if not line:
            continue
        if line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), styles["heading"]))
        elif line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), styles["title"]))
        else:
            story.append(Paragraph(inline(line), styles["body"]))
    flush()

    document.build(story or [Paragraph("Empty report", styles["body"])])
    return buffer.getvalue()
