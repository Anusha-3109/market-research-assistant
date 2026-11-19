"""Tests for the usage log and the Dashboard page.

Every question leaves one line in the log: when it was asked, whether it
was answered, turned away by the guard or failed, how long it took, what
it used and which tools ran. The Dashboard reads the log. Each account
sees its own lines; on your own computer (no accounts) every line counts.
"""

from datetime import datetime, timedelta, timezone

from langchain_core.messages import AIMessage
from langgraph.store.memory import InMemoryStore

from agent.usage import Usage
from agent.usage_log import (
    ANSWERED,
    ASSISTANT,
    ERROR,
    TURNED_AWAY,
    events,
    per_day,
    record,
    summary,
)
from tests.test_app import button, make_runtime, page  # noqa: F401  (page is a fixture)
from tests.test_language import switch

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def used(cost=0.01, read=1000, written=200):
    return Usage(calls=2, input_tokens=read, output_tokens=written, cost=cost, priced_calls=2)


def a_log() -> InMemoryStore:
    store = InMemoryStore()
    record(store, "u-anna", ANSWERED, seconds=6.0, usage=used(0.01), tools=["web_search"],
           thread="t1", when=NOW - timedelta(days=1))
    record(store, "u-anna", ANSWERED, seconds=40.0, usage=used(0.03, 9000, 900),
           tools=["create_market_report"], report=True, sources=11, thread="t2", when=NOW)
    record(store, "u-anna", TURNED_AWAY, when=NOW)
    record(store, "u-anna", ERROR, seconds=3.0, error="The request took too long and was stopped.",
           tools=["web_search"], thread="t3", when=NOW)
    record(store, "u-anna", ASSISTANT, usage=used(0.001, 300, 50), when=NOW)
    record(store, "u-ben", ANSWERED, seconds=5.0, usage=used(0.02), tools=["search_news"], when=NOW)
    record(store, "u-anna", ANSWERED, seconds=7.0, usage=used(0.05), tools=["web_search"],
           when=NOW - timedelta(days=40))
    return store


# --- the log ---------------------------------------------------------------------------------------

def test_a_line_keeps_what_happened_and_is_read_back_oldest_first():
    lines = events(a_log(), "u-anna")

    assert [line["kind"] for line in lines][:2] == [ANSWERED, ANSWERED]
    assert lines[0]["at"] < lines[-1]["at"]
    report = next(line for line in lines if line.get("report"))
    assert (report["seconds"], report["cost"], report["tools"], report["sources"]) == \
        (40.0, 0.03, ["create_market_report"], 11)


def test_each_account_reads_only_its_own_lines_and_no_account_reads_all():
    store = a_log()

    assert {line["user"] for line in events(store, "u-ben")} == {"u-ben"}
    assert {line["user"] for line in events(store, None)} == {"u-anna", "u-ben"}


def test_lines_before_the_range_are_left_out():
    assert len(events(a_log(), "u-anna", since=NOW - timedelta(days=30))) == 5


def test_the_summary_counts_requests_answers_wait_tokens_and_cost():
    lines = events(a_log(), "u-anna", since=NOW - timedelta(days=30))

    figures = summary(lines)

    assert figures["requests"] == 4                     # the assistant's chat is not a request
    assert figures["answered"] == 2
    assert figures["share_answered"] == 0.5
    assert figures["median_seconds"] == 23.0            # of the two answered: 6 and 40
    assert figures["tokens"] == 1200 + 9900 + 350
    assert round(figures["cost"], 4) == 0.041           # 0.01 + 0.03 + the assistant's 0.001
    assert figures["reports"] == 1 and figures["single"] == 1 and figures["sources"] == 11
    assert figures["conversations"] == 2
    assert figures["turned_away"] == 1 and figures["errors"] == 1
    assert figures["tools"] == {"web_search": 2, "create_market_report": 1}


def test_per_day_has_one_row_for_every_day_in_the_range_also_quiet_ones():
    lines = events(a_log(), "u-anna", since=NOW - timedelta(days=6))

    days = per_day(lines, NOW.date(), days=7)

    assert len(days) == 7
    today = days[-1]
    assert (today["answered"], today["turned_away"], today["error"]) == (1, 1, 1)
    assert days[0]["answered"] == 0 and days[0]["cost"] == 0


# --- written by the app ------------------------------------------------------------------------

def test_an_answered_question_leaves_a_line(page, tmp_path):  # noqa: F811
    runtime = make_runtime(tmp_path, [AIMessage("An answer.")])
    app = page(runtime=runtime)

    app.chat_input[0].set_value("How big is HelloFresh?").run()

    lines = events(runtime.store, None)
    assert [line["kind"] for line in lines] == [ANSWERED]
    assert lines[0]["seconds"] >= 0


def test_a_question_the_guard_turns_away_leaves_a_line(page, tmp_path):  # noqa: F811
    runtime = make_runtime(tmp_path, [])
    app = page(runtime=runtime)

    app.chat_input[0].set_value("   ").run()

    assert [line["kind"] for line in events(runtime.store, None)] == [TURNED_AWAY]


# --- the Dashboard page --------------------------------------------------------------------------

def open_dashboard(page, tmp_path, store=None):  # noqa: F811
    runtime = make_runtime(tmp_path, [], store=store)
    app = page(runtime=runtime)
    button(app, "page_dashboard").click().run()
    assert not app.exception
    return app


def cards(app) -> str:
    return "\n".join(element.proto.body for element in app.get("html")
                     if "gw-kpi" in element.proto.body)


def test_the_dashboard_shows_five_figure_cards(page, tmp_path):  # noqa: F811
    store = InMemoryStore()
    now = datetime.now(timezone.utc)
    record(store, "local", ANSWERED, seconds=8.0, usage=used(0.02), tools=["web_search"], when=now)
    record(store, "local", TURNED_AWAY, when=now)

    app = open_dashboard(page, tmp_path, store)

    shown = cards(app)
    for label in ("Requests", "Answered", "Typical wait", "Tokens", "Cost"):
        assert label in shown, label
    assert ">2<" in shown and ">50%<" in shown and ">8.0 s<" in shown and ">$0.02<" in shown


def test_the_dashboard_has_its_charts_a_range_picker_and_the_cards_below(page, tmp_path):  # noqa: F811
    app = open_dashboard(page, tmp_path, InMemoryStore())

    assert any(c.key == "dashboard_range" for c in app.segmented_control)
    titles = [h.value for h in app.subheader] + [m.value for m in app.markdown]
    for title in ("Requests per day", "Time to answer", "Tokens per day", "Cost per day",
                  "Tool calls", "How the guard sorted questions", "Errors"):
        assert any(title in text for text in titles), title
    assert len(app.chat_input) == 0


def test_the_dashboard_follows_the_language(page, tmp_path):  # noqa: F811
    app = open_dashboard(page, tmp_path, InMemoryStore())

    switch(app).set_value("de").run()

    assert "Anfragen" in cards(app) and "Kosten" in cards(app)
