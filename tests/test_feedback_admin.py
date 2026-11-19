"""Tests for the Feedback tab of the Admin page.

It shows how the answers were rated in the last seven days: the share
rated helpful, the thumbs down and their reasons, which settings were
rated best, and the latest thumbs down with their comments. Its switch
"Learn from feedback" turns the tips in the prompt on or off for everyone.
"""

from datetime import datetime, timedelta, timezone

from langchain_core.messages import AIMessage
from langgraph.store.memory import InMemoryStore

from agent.app_settings import load_app_settings
from agent.memory import DEFAULT_USER
from agent.feedback import DOWN, TIPS, UP, explain, feedback_summary, rate, ratings
from agent.usage_log import ANSWERED, record
from tests.test_admin import back, listening_app, open_admin, widget
from tests.test_app import make_runtime, page  # noqa: F401  (page is a fixture)

NOW = datetime.now(timezone.utc)
MINI = {"model": "openai/gpt-4.1-mini", "style": "Balanced", "length": "medium"}
FULL = {"model": "openai/gpt-4.1", "style": "Detailed", "length": "medium"}


def a_week_of_ratings(store) -> None:
    """Four ratings this week (three helpful), one from last month, and
    eight answers in the usage log."""
    def one(user, thread, rating, settings, days_ago, reasons=(), comment="", question="Q"):
        rate(store, user, thread, 0, rating, question=question, settings=settings,
             when=NOW - timedelta(days=days_ago))
        if reasons or comment:
            explain(store, user, thread, 0, list(reasons), comment)

    one("u-anna", "t1", UP, MINI, 3)
    one("u-anna", "t2", UP, MINI, 2)
    one("u-ben", "t3", UP, FULL, 1)
    one("u-ben", "t4", DOWN, MINI, 0, ["too_long", "missing_sources"], "Top <b>3</b> only.",
        question="Who sells <i>oat milk</i>?")
    one("u-anna", "t0", DOWN, MINI, 40, ["wrong_facts"])
    for _ in range(8):
        record(store, "u-anna", ANSWERED, seconds=5.0, when=NOW - timedelta(hours=1))


# --- the figures -----------------------------------------------------------------------------------

def test_the_summary_counts_the_ratings_of_the_week():
    store = InMemoryStore()
    a_week_of_ratings(store)

    figures = feedback_summary(ratings(store, None, since=NOW - timedelta(days=7)), answered=8)

    assert (figures["ratings"], figures["helpful"], figures["down"]) == (4, 0.75, 1)
    assert figures["with_comment"] == 1
    assert figures["reasons"] == {"missing_sources": 1, "too_long": 1}
    assert figures["top_reason"] == "missing_sources"
    assert figures["rated_share"] == 0.5


def test_the_summary_compares_the_settings_most_rated_first():
    store = InMemoryStore()
    a_week_of_ratings(store)

    rows = feedback_summary(ratings(store, None, since=NOW - timedelta(days=7)), answered=8)["by_setting"]

    assert rows == [{"model": "openai/gpt-4.1-mini", "style": "Balanced", "ratings": 3, "helpful": 2 / 3},
                    {"model": "openai/gpt-4.1", "style": "Detailed", "ratings": 1, "helpful": 1.0}]


def test_the_latest_thumbs_down_come_newest_first_and_no_ratings_give_no_shares():
    store = InMemoryStore()
    a_week_of_ratings(store)

    latest = feedback_summary(ratings(store, None), answered=0)["latest_down"]
    empty = feedback_summary([], answered=0)

    assert [line["thread"] for line in latest] == ["t4", "t0"]
    assert (empty["helpful"], empty["rated_share"], empty["top_reason"]) == (None, None, None)


# --- the tab ---------------------------------------------------------------------------------------

def admin_with_ratings(page, tmp_path):  # noqa: F811
    store = InMemoryStore()
    a_week_of_ratings(store)
    return open_admin(page(runtime=make_runtime(tmp_path, [], store=store)))


def cards(app) -> str:
    return "\n".join(e.proto.body for e in app.get("html") if "gw-kpi" in e.proto.body)


def test_the_admin_page_has_a_feedback_tab(page, tmp_path):  # noqa: F811
    app = admin_with_ratings(page, tmp_path)

    assert [tab.label for tab in app.tabs] == ["Developer settings", "Feedback", "Documentation"]
    shown = cards(app)
    for label in ("Thumbs down", "Most common reason", "Answers rated"):
        assert label in shown, label
    assert "75%" in shown and "3 of 4 ratings" in shown and "Missing sources" in shown


def test_the_helpful_card_of_the_settings_tab_shows_the_real_share(page, tmp_path):  # noqa: F811
    app = admin_with_ratings(page, tmp_path)

    assert "No ratings yet" not in cards(app)


def test_the_latest_thumbs_down_show_question_reasons_and_comment_as_text(page, tmp_path):  # noqa: F811
    app = admin_with_ratings(page, tmp_path)

    latest = "\n".join(e.proto.body for e in app.get("html") if "gw-down" in e.proto.body)
    assert "Who sells &lt;i&gt;oat milk&lt;/i&gt;?" in latest
    assert "Top &lt;b&gt;3&lt;/b&gt; only." in latest
    assert "Too long" in latest and "ben" in latest
    assert "<i>oat milk</i>" not in latest


def test_learning_is_on_at_first_and_switching_it_off_keeps_the_tips_out(page, tmp_path):  # noqa: F811
    app, model, runtime = listening_app(page, tmp_path)
    for thread in ("t1", "t2"):
        rate(runtime.store, DEFAULT_USER, thread, 0, DOWN, question="Q", settings=MINI)
        explain(runtime.store, DEFAULT_USER, thread, 0, ["too_long"], "")
    open_admin(app)
    assert widget(app, "admin_learn").value is True

    widget(app, "admin_learn").set_value(False).run()
    back(app).chat_input[0].set_value("How big is the oat milk market?").run()

    assert load_app_settings(runtime.store)["learn"] is False
    assert TIPS["too_long"] not in model.told()


def test_with_learning_on_the_tips_reach_the_model(page, tmp_path):  # noqa: F811
    app, model, runtime = listening_app(page, tmp_path)
    for thread in ("t1", "t2"):
        rate(runtime.store, DEFAULT_USER, thread, 0, DOWN, question="Q", settings=MINI)
        explain(runtime.store, DEFAULT_USER, thread, 0, ["too_long"], "")

    app.chat_input[0].set_value("How big is the oat milk market?").run()

    assert TIPS["too_long"] in model.told()


def test_the_tab_is_in_german(page, tmp_path):  # noqa: F811
    from tests.test_language import switch as language_switch
    app = admin_with_ratings(page, tmp_path)

    language_switch(app).set_value("de").run()

    assert [tab.label for tab in app.tabs][1] == "Feedback"
    assert "Daumen runter" in cards(app)
    assert widget(app, "admin_learn").label == "Aus Feedback lernen"


def test_no_ratings_yet_says_so(page, tmp_path):  # noqa: F811
    app = open_admin(page(runtime=make_runtime(tmp_path, [AIMessage("ok")])))

    assert "No ratings yet" in cards(app)
