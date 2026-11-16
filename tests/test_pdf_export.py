"""Tests for the PDF export. A real PDF is built each time; the tests check
that it is a valid file, that links survive, and that the markup is
converted safely. How the pages look was checked by eye."""

import re

from agent import pdf_export

REPORT = """# Market research report: meal kits in Germany

Prepared on 2026-11-16 from public sources.

## 1. Market overview
- The market was worth €1 billion in 2025. [source](https://a.example/market)
- Growth is **8-10%** a year.

## 3. Pricing
| Company | Product or plan | Price | Source |
|---|---|---|---|
| Löwenanteil | Bio-Gericht | 7,99 € | [company website](https://www.loewenanteil.com) |
| HelloFresh | not found | not found | [checked](https://www.hellofresh.de) |

## 6. References
1. https://a.example/market
2. https://www.loewenanteil.com
"""


def make() -> bytes:
    return pdf_export.report_to_pdf(REPORT)


def test_the_result_is_a_pdf_file():
    pdf = make()

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 1500


def test_links_in_the_report_are_clickable_in_the_pdf():
    pdf = make()

    assert b"https://a.example/market" in pdf
    assert b"https://www.loewenanteil.com" in pdf
    assert b"/URI" in pdf                       # PDF's marker for a web link


def test_markdown_markup_is_converted_not_printed():
    markup = pdf_export.inline("Growth is **8-10%** a year, see [source](https://a.example).")

    assert markup == ('Growth is <b>8-10%</b> a year, see '
                      '<a href="https://a.example" color="#185FA5">source</a>.')


def test_a_bare_address_becomes_a_link():
    assert pdf_export.inline("1. https://a.example/m") == (
        '1. <a href="https://a.example/m" color="#185FA5">https://a.example/m</a>')


def test_angle_brackets_from_a_web_page_are_shown_as_text():
    # Text that came from the web must not be able to act as markup.
    assert pdf_export.inline("Box <b>big</b> & <script>") == \
        "Box &lt;b&gt;big&lt;/b&gt; &amp; &lt;script&gt;"


def test_the_euro_sign_and_umlauts_survive():
    assert pdf_export.printable("7,99 € bei Löwenanteil") == "7,99 € bei Löwenanteil"


def test_a_character_the_font_cannot_draw_is_replaced_not_fatal():
    assert pdf_export.printable("rising ↗ fast") == "rising ? fast"
    assert pdf_export.report_to_pdf("# Title ↗\n\nText 中文").startswith(b"%PDF-")


def test_table_lines_are_split_into_cells_and_the_separator_is_skipped():
    assert pdf_export.parse_table_row("| Company | Price |") == ["Company", "Price"]
    assert pdf_export.parse_table_row("|---|:-:|") is None


def test_an_empty_report_still_gives_a_valid_pdf():
    assert pdf_export.report_to_pdf("").startswith(b"%PDF-")


def test_a_long_report_runs_over_several_pages():
    long_report = "# Title\n\n" + "\n\n".join(f"Paragraph {n} " + "word " * 80 for n in range(60))

    pdf = pdf_export.report_to_pdf(long_report)

    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) > 2
