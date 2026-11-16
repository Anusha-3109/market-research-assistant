"""Tests for numbered citations and the source list."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import session
from agent.citations import (
    domain_of,
    number_citations,
    site_named_in,
    title_from_url,
    titles_in_results,
    without_references,
)


# --- small helpers ----------------------------------------------------------------------

def test_domain_of_drops_www_and_the_path():
    assert domain_of("https://www.prepmymeal.com/boxes?x=1") == "prepmymeal.com"
    assert domain_of("https://finance.yahoo.com/quote/HFG.DE") == "finance.yahoo.com"


def test_titles_are_read_from_search_results():
    output = ("Source used: Tavily\n\n"
              "[1] Prepmymeal Boxen\nURL: https://prepmymeal.com/boxen/\nText\n\n"
              "[2] Meal kits in Germany\nURL: https://m.example/report\nMore text")

    assert titles_in_results(output) == {
        "https://prepmymeal.com/boxen": "Prepmymeal Boxen",
        "https://m.example/report": "Meal kits in Germany",
    }


def test_a_page_without_a_known_title_is_named_from_its_address():
    assert title_from_url("https://prepmymeal.com/collections/mix-linie") == \
        "prepmymeal.com: collections / mix linie"
    assert title_from_url("https://www.eatfitter.de/") == "eatfitter.de"


# --- numbering -----------------------------------------------------------------------------

def test_each_link_becomes_a_number_and_a_source():
    text, sources = number_citations(
        "A box costs €5.93 [source](https://a.example/p). Sales rose [source](https://b.example/n).")

    assert text == ("A box costs €5.93 [[1]](https://a.example/p). "
                    "Sales rose [[2]](https://b.example/n).")
    assert [(s.number, s.domain) for s in sources] == [(1, "a.example"), (2, "b.example")]


def test_a_page_cited_twice_keeps_one_number():
    text, sources = number_citations(
        "One [source](https://a.example/p). Two [source](https://b.example). "
        "Three [source](https://a.example/p/).")

    assert text.count("[[1]]") == 2
    assert len(sources) == 2


def test_meaningful_link_words_are_kept_in_front_of_the_number():
    text, sources = number_citations("See [Yahoo Finance](https://finance.yahoo.com/quote/X).")

    assert text == "See Yahoo Finance [[1]](https://finance.yahoo.com/quote/X)."
    assert sources[0].title == "Yahoo Finance"


def test_a_known_page_title_is_preferred_over_the_link_words():
    _, sources = number_citations(
        "Price [source](https://a.example/p).", titles={"https://a.example/p": "Alpha pricing"})

    assert sources[0].title == "Alpha pricing"


def test_a_very_long_title_is_shortened():
    _, sources = number_citations(
        "Price [source](https://a.example/p).", titles={"https://a.example/p": "x" * 200})

    assert len(sources[0].title) == 71 and sources[0].title.endswith("…")


def test_text_without_links_is_unchanged_and_has_no_sources():
    assert number_citations("No links here.") == ("No links here.", [])


# --- official sources -------------------------------------------------------------------------

def test_a_listed_company_site_is_marked_official():
    _, sources = number_citations(
        "Price [source](https://www.prepmymeal.com/boxes). Review [source](https://blog.example/x).",
        official_domains={"prepmymeal.com"})

    assert [s.official for s in sources] == [True, False]


def test_a_site_named_in_the_question_is_marked_official():
    _, sources = number_citations(
        "Price [source](https://prepmymeal.com/boxes).",
        subject="What does Prepmymeal charge?")

    assert sources[0].official


def test_a_short_site_name_is_not_matched_by_chance():
    # "faz" appears inside many words; three letters are too few to trust.
    assert not site_named_in("Is the market amazing?", "https://www.faz.net/x")
    assert site_named_in("How big is HelloFresh?", "https://www.hellofresh.de/")


def test_two_ordinary_words_do_not_add_up_to_a_site_name():
    assert not site_named_in("A market research report on meal kits",
                             "https://www.marketresearch.com/x")


# --- reports ---------------------------------------------------------------------------------

REPORT = ("# Market research report: meal kits in Germany\n\n"
          "## 1. Market overview\n- Worth €1 billion [source](https://a.example/m).\n\n"
          "## 6. References\n1. https://a.example/m\n")


def test_the_reference_list_is_left_out_of_the_displayed_report():
    shown = without_references(REPORT)

    assert "## 1. Market overview" in shown
    assert "References" not in shown


def test_text_without_a_reference_list_is_left_alone():
    assert without_references("Just an answer.") == "Just an answer."


# --- through the conversation ------------------------------------------------------------------

def test_an_answer_gets_citations_with_titles_from_its_own_search():
    blocks = session.to_blocks([
        HumanMessage("What does Prepmymeal charge?"),
        AIMessage("", tool_calls=[{"name": "web_search", "id": "1",
                                   "args": {"query": "Prepmymeal Preise"}}]),
        ToolMessage("Source used: Tavily\n\n[1] Prepmymeal Boxen\n"
                    "URL: https://prepmymeal.com/boxen\nText",
                    tool_call_id="1", name="web_search"),
        AIMessage("A box costs €5.93 [source](https://prepmymeal.com/boxen)."),
    ])

    answer = blocks[1]
    assert answer.cited == "A box costs €5.93 [[1]](https://prepmymeal.com/boxen)."
    assert answer.sources[0].title == "Prepmymeal Boxen"
    assert answer.sources[0].official
    # What is stored is untouched, for saving and downloading.
    assert answer.text == "A box costs €5.93 [source](https://prepmymeal.com/boxen)."


def test_titles_from_one_question_do_not_leak_into_the_next():
    blocks = session.to_blocks([
        HumanMessage("First"),
        ToolMessage("[1] First title\nURL: https://a.example/p", tool_call_id="1",
                    name="web_search"),
        AIMessage("One [source](https://a.example/p)."),
        HumanMessage("Second"),
        AIMessage("Two [source](https://a.example/p)."),
    ])

    assert blocks[1].sources[0].title == "First title"
    assert blocks[3].sources[0].title == "a.example: p"


def test_a_report_uses_the_titles_and_official_sites_the_workflow_passed_on():
    report_message = ToolMessage(
        REPORT, tool_call_id="1", name="create_market_report",
        artifact={"problems": [], "log": [],
                  "titles": {"https://a.example/m": "German meal kit market"},
                  "official": ["a.example"]})

    block = session.to_blocks([HumanMessage("Report please"), report_message])[1]

    assert "References" not in block.cited
    assert "[[1]](https://a.example/m)" in block.cited
    assert block.sources[0].title == "German meal kit market"
    assert block.sources[0].official
    assert "## 6. References" in block.report        # the stored report is complete


# --- turns --------------------------------------------------------------------------------------

def test_each_question_is_paired_with_its_answer():
    turns = session.to_turns(session.to_blocks([
        HumanMessage("First"), AIMessage("One"),
        HumanMessage("Second"), AIMessage("Two"),
    ]))

    assert [(t.question, t.answer.text) for t in turns] == [("First", "One"), ("Second", "Two")]


def test_a_question_still_being_answered_has_no_answer_yet():
    turns = session.to_turns(session.to_blocks([HumanMessage("First"), AIMessage("One"),
                                                HumanMessage("Second")]))

    assert turns[1].question == "Second"
    assert turns[1].answer is None


def test_short_title_keeps_one_line_within_the_limit():
    assert session.short_title("A  question\nover two lines") == "A question over two lines"
    assert session.short_title("x" * 100, limit=10) == "x" * 10 + "…"
