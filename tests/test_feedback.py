"""Tests for rating an answer: thumbs up or down under each answer.

A rating is saved in the long-term store under ("feedback", account id),
one per answer, with what is needed to learn from it later: the question
and the settings the answer was written with. Clicking again changes it.
"""

from datetime import datetime, timezone

from langchain_core.messages import AIMessage
from langgraph.store.memory import InMemoryStore
from streamlit.testing.v1 import AppTest

from agent.feedback import DOWN, UP, rate, rating_of, ratings
from tests.test_app import APP, page  # noqa: F401  (page is a fixture)
from tests.test_ask_view import ask, two_questions
from tests.test_language import switch as language_switch
from tests.test_views import with_a_report
from ui import runtime as ui_runtime

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
SETTINGS = {"model": "openai/gpt-4.1-mini", "style": "balanced", "length": "medium"}


def thumbs(app, index: int):
    return next(widget for widget in app.feedback if widget.key.endswith(f"_{index}"))


# --- saving a rating -------------------------------------------------------------------------------

def test_a_rating_is_saved_with_the_question_and_the_settings_used():
    store = InMemoryStore()

    rate(store, "u-anna", "t1", 0, UP, question="Stroller brands in Italy?",
         settings=SETTINGS, report=False, when=NOW)

    assert rating_of(store, "u-anna", "t1", 0) == UP
    [line] = ratings(store, "u-anna")
    assert (line["question"], line["model"], line["style"], line["length"], line["report"]) == \
        ("Stroller brands in Italy?", "openai/gpt-4.1-mini", "balanced", "medium", False)
    assert line["at"] == NOW.isoformat()


def test_rating_again_changes_the_rating_and_none_takes_it_back():
    store = InMemoryStore()
    rate(store, "u-anna", "t1", 0, UP, question="Q", settings=SETTINGS)

    rate(store, "u-anna", "t1", 0, DOWN, question="Q", settings=SETTINGS)
    assert rating_of(store, "u-anna", "t1", 0) == DOWN
    assert len(ratings(store, "u-anna")) == 1

    rate(store, "u-anna", "t1", 0, None, question="Q", settings=SETTINGS)
    assert rating_of(store, "u-anna", "t1", 0) is None
    assert ratings(store, "u-anna") == []


def test_each_account_has_its_own_ratings_and_no_account_reads_all():
    store = InMemoryStore()
    rate(store, "u-anna", "t1", 0, UP, question="Q", settings=SETTINGS)
    rate(store, "u-ben", "t2", 0, DOWN, question="Q", settings=SETTINGS)

    assert [line["user"] for line in ratings(store, "u-ben")] == ["u-ben"]
    assert {line["user"] for line in ratings(store, None)} == {"u-anna", "u-ben"}
    assert rating_of(store, "u-anna", "t2", 0) is None


def test_a_very_long_question_is_cut_short():
    store = InMemoryStore()

    rate(store, "u-anna", "t1", 0, UP, question="x" * 2000, settings=SETTINGS)

    assert len(ratings(store, "u-anna")[0]["question"]) <= 300


# --- on the page -----------------------------------------------------------------------------------

def test_every_answer_has_thumbs_and_a_click_saves_the_rating(page):  # noqa: F811
    app = two_questions(page)

    assert [widget.value for widget in app.feedback] == [None, None]

    thumbs(app, 1).set_value(DOWN).run()

    assert not app.exception
    [line] = ratings(app.runtime.store, None)
    assert (line["index"], line["rating"], line["question"]) == (1, DOWN, "Second question")


def test_the_rating_is_shown_again_when_the_conversation_is_opened_again(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "A question")
    thumbs(app, 0).set_value(UP).run()

    # A new visit to the same address, as after a refresh.
    again = AppTest.from_file(APP, default_timeout=30)
    again.query_params["c"] = app.query_params["c"]
    again.run()

    assert thumbs(again, 0).value == UP


def test_a_report_can_be_rated_in_the_report_view(page, tmp_path):  # noqa: F811
    app = with_a_report(page, tmp_path)
    next(b for b in app.button if b.key == "open_report_0").click().run()

    thumbs(app, 0).set_value(UP).run()

    [line] = ratings(ui_runtime.get_store(), None)         # the fake agent's store
    assert (line["rating"], line["report"]) == (UP, True)


def test_the_question_beside_the_thumbs_is_in_german(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "A question")
    assert "Was this helpful?" in [caption.value for caption in app.caption]

    language_switch(app).set_value("de").run()

    assert "War das hilfreich?" in [caption.value for caption in app.caption]


def test_an_answer_still_being_written_has_no_thumbs(page):  # noqa: F811
    app = page()

    assert list(app.feedback) == []
