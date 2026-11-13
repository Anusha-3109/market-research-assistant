"""Tests for the report checker, using sample reports."""

from agent.report_check import check_report, format_check, table_rows

GOOD_REPORT = """# Market research report: meal kits in Germany

## 1. Market overview
- The German market was worth €1 billion in 2025 [source](https://a.example/market).

## 2. Competitors

| Company | What they offer | Size or financials | Source |
|---------|-----------------|--------------------|--------|
| HelloFresh SE | Meal kits | Revenue: €6.2 billion | [Yahoo](https://finance.yahoo.com/quote/HFG.DE) |
| Prepmymeal | Frozen meals | not found | [site](https://prepmymeal.example) |

## 3. Pricing

| Company | Product or plan | Price | Source | Date found |
|---------|-----------------|-------|--------|------------|
| HelloFresh | Box for 2 | €45 per week | [shop](https://hellofresh.example/plans) | 2026-11-13 |
| Prepmymeal | 6 meals | not found | [site](https://prepmymeal.example) | 2026-11-13 |

## 4. Trends
- Search interest is rising, +27% [source](https://trends.google.com/x).

## 5. SWOT analysis
This section is the assistant's own analysis, based on the facts above.

**Strengths:**
- Growing demand.

## 6. References
1. https://a.example/market
"""


def without(report: str, text: str, replacement: str = "") -> str:
    assert text in report
    return report.replace(text, replacement)


def test_a_complete_report_passes():
    assert check_report(GOOD_REPORT) == []


def test_swot_bullets_do_not_need_sources():
    # "- Growing demand." has no link and must not be reported.
    assert not any("SWOT" in problem for problem in check_report(GOOD_REPORT))


def test_a_missing_section_is_reported():
    report = GOOD_REPORT[:GOOD_REPORT.index("## 4. Trends")] + \
        GOOD_REPORT[GOOD_REPORT.index("## 5. SWOT analysis"):]

    assert check_report(report) == ['Section "4. Trends" is missing']


def test_a_fact_without_a_source_link_is_reported():
    report = without(GOOD_REPORT, " [source](https://a.example/market).", ".")

    problems = check_report(report)

    assert len(problems) == 1
    assert problems[0].startswith('Section "1. Market overview" has a bullet without a source link')


def test_a_table_row_without_a_source_link_is_reported():
    report = without(GOOD_REPORT, "| [site](https://prepmymeal.example) | 2026-11-13 |",
                     "| company website | 2026-11-13 |")

    assert check_report(report) == [
        'Section "3. Pricing" has a row without a source link: "Prepmymeal"']


def test_a_competitor_without_a_price_row_is_reported():
    report = without(
        GOOD_REPORT,
        "| Prepmymeal | 6 meals | not found | [site](https://prepmymeal.example) | 2026-11-13 |\n")

    assert check_report(report) == [
        'Competitor "Prepmymeal" has no row in the Pricing table']


def test_company_names_match_even_when_one_has_a_legal_suffix():
    # "HelloFresh SE" in Competitors and "HelloFresh" in Pricing are the same.
    assert not any("HelloFresh" in problem for problem in check_report(GOOD_REPORT))


def test_a_missing_swot_label_is_reported():
    report = without(GOOD_REPORT,
                     "This section is the assistant's own analysis, based on the facts above.\n")

    assert check_report(report) == [
        "The SWOT section is not labelled as the assistant's own analysis"]


def test_an_empty_references_section_is_reported():
    report = without(GOOD_REPORT, "1. https://a.example/market\n", "None.\n")

    assert check_report(report) == ["The References section lists no links"]


def test_a_section_with_no_table_is_reported():
    start = GOOD_REPORT.index("| Company | Product or plan")
    end = GOOD_REPORT.index("## 4. Trends")
    report = GOOD_REPORT[:start] + "No prices were found.\n\n" + GOOD_REPORT[end:]

    problems = check_report(report)

    assert 'Section "3. Pricing" has no table rows' in problems


def test_table_rows_skips_the_header_and_the_separator():
    table = "| A | B |\n|---|:-:|\n| one | two |\n"

    assert table_rows(table) == [["one", "two"]]


def test_format_check_says_passed_or_lists_the_issues():
    assert format_check([]) == "Report check: passed"
    assert format_check(["First", "Second"]) == "Report check: 2 issues\n- First\n- Second"
    assert format_check(["Only one"]).startswith("Report check: 1 issue\n")
