"""Tests for the Report view: the sections of a report as cards, each with
a status, beside a box with the contents and the ways to keep the report.

The page is run without a browser, with a fake agent.
"""

from langchain_core.messages import AIMessage, ToolMessage
from streamlit.testing.v1 import AppTest

from agent.session import report_sections, section_status
from tests.test_app import APP, button, make_runtime, page, texts  # noqa: F401  (page is a fixture)

REPORT = """# Market research report: oat milk in Germany

Prepared on 2026-11-18 from public sources.

## 1. Market overview

- Oat milk market value: 1 billion EUR (Germany, 2025). [source](https://a.example/market)
- Growth: 8% a year (Germany, 2026-2030). [source](https://b.example/growth)

## 2. Competitors

| Company | Price |
|---|---|
| Oatly | 2.49 EUR [source](https://oatly.example/shop) |
| Alpro | not found |
| Kölln | not found |

## 3. SWOT

**Strengths:** a growing market.
"""


def with_report(page, tmp_path, report=REPORT):  # noqa: F811
    """The page opened at a conversation that holds this report, on the
    Report view."""
    runtime = make_runtime(tmp_path, [])
    wants = AIMessage("", tool_calls=[{"name": "create_market_report", "id": "r1",
                                       "args": {"product": "oat milk", "country": "Germany"}}])
    result = ToolMessage(report, tool_call_id="r1", name="create_market_report",
                         artifact={"problems": [], "log": []})
    runtime.agent.update_state({"configurable": {"thread_id": "rep"}}, {"messages": [
        {"role": "user", "content": "A report on oat milk in Germany"}, wants, result]},
        as_node="tools")
    page(runtime=runtime)
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["c"] = "rep"
    app.run()
    button(app, "view_report").click().run()
    return app


def html_with(app, marker: str) -> list[str]:
    return [element.proto.body for element in app.get("html") if marker in element.proto.body]


# --- reading the sections out of a report ------------------------------------------------------

def test_a_report_is_split_at_its_section_headings():
    intro, sections = report_sections(REPORT)

    assert "Prepared on 2026-11-18 from public sources." in intro
    assert [section.title for section in sections] == ["1. Market overview", "2. Competitors", "3. SWOT"]
    assert sections[0].body.startswith("- Oat milk market value: 1 billion EUR")
    assert "## " not in sections[0].body
    assert "Oatly" in sections[1].body and "Oat milk market value" not in sections[1].body


def test_the_reports_own_title_line_is_not_part_of_the_introduction():
    intro, _ = report_sections(REPORT)

    assert "# Market research report" not in intro


def test_a_text_without_section_headings_is_all_introduction():
    intro, sections = report_sections("Just a short note.\n\nNothing else.")

    assert sections == []
    assert intro == "Just a short note.\n\nNothing else."


# --- the status of a section ---------------------------------------------------------------------

def test_a_section_with_missing_values_says_how_many():
    _, sections = report_sections(REPORT)

    assert section_status(sections[1].body) == ("2 not found", "warn")


def test_a_section_with_only_sourced_facts_says_how_many_sources():
    body = "- A [[1]](https://a.example) and B [[2]](https://b.example) and A again [[1]](https://a.example)."

    assert section_status(body) == ("2 sources", "ok")
    assert section_status("- One fact [[3]](https://c.example).") == ("1 source", "ok")


def test_a_section_without_sources_or_gaps_has_no_status():
    assert section_status("**Strengths:** a growing market.") is None


# --- on the page ---------------------------------------------------------------------------------

def test_every_section_is_a_card_with_its_title(page, tmp_path):  # noqa: F811
    app = with_report(page, tmp_path)

    assert not app.exception
    titles = "\n".join(html_with(app, 'class="gw-section-title"'))
    assert "1. Market overview" in titles and "2. Competitors" in titles and "3. SWOT" in titles
    assert "Oat milk market value: 1 billion EUR (Germany, 2025)." in texts(app)


def test_a_card_shows_the_status_of_its_section(page, tmp_path):  # noqa: F811
    app = with_report(page, tmp_path)

    cards = html_with(app, 'class="gw-section-title"')
    assert "2 sources" in next(card for card in cards if "1. Market overview" in card)
    assert "2 not found" in next(card for card in cards if "2. Competitors" in card)
    assert "gw-section-tag" not in next(card for card in cards if "3. SWOT" in card)


def test_the_contents_box_lists_the_sections_in_order(page, tmp_path):  # noqa: F811
    app = with_report(page, tmp_path)

    [contents] = html_with(app, 'class="gw-contents"')
    assert contents.index("1. Market overview") < contents.index("2. Competitors") < contents.index("3. SWOT")
    assert "Oat milk in Germany" in contents


def test_the_report_can_be_downloaded_and_saved_from_the_contents_box(page, tmp_path):  # noqa: F811
    app = with_report(page, tmp_path)

    assert [b.label for b in app.get("download_button")] == ["Markdown", "PDF"]
    assert button(app, "save_0").label == "Save to reports folder"


def test_the_sources_of_the_report_are_listed(page, tmp_path):  # noqa: F811
    app = with_report(page, tmp_path)

    sources = "\n".join(html_with(app, "gw-sources-head"))
    assert "a.example" in sources and "oatly.example" in sources


def test_a_section_title_is_shown_as_text_never_as_markup(page, tmp_path):  # noqa: F811
    app = with_report(page, tmp_path,
                      report=REPORT.replace("## 3. SWOT", "## 3. <b>SWOT</b>"))

    assert "3. &lt;b&gt;SWOT&lt;/b&gt;" in "\n".join(html_with(app, 'class="gw-section-title"'))
