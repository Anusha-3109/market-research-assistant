"""Tests for the Ask view: a conversation as one full-width chat, with
every question and its answer, suggestions for a next question, and the
question box.

The page is run without a browser, with a fake agent.
"""

from langchain_core.messages import AIMessage

from agent.session import Block, reply_summary, steps_for_thread, steps_while_working
from tests.test_app import button, page, texts  # noqa: F401  (page is a fixture)
from tests.test_views import with_a_report


def bubbles(app) -> list[str]:
    """The questions shown in the chat, oldest first, as HTML."""
    return [element.proto.body for element in app.get("html")
            if 'class="gw-ask-question"' in element.proto.body]


def suggestions(app) -> list[str]:
    return [b.label for b in app.button if (b.key or "").startswith("suggest_")]


def ask(app, question: str):
    app.chat_input[0].set_value(question).run()
    return app


def two_questions(page):  # noqa: F811
    app = page([AIMessage("First answer."), AIMessage("Second answer.")])
    ask(app, "First question")
    return ask(app, "Second question")


# --- the chat ------------------------------------------------------------------------------------

def test_every_question_and_every_answer_is_in_the_chat_oldest_first(page):  # noqa: F811
    app = two_questions(page)

    assert not app.exception
    assert ["First question" in bubbles(app)[0], "Second question" in bubbles(app)[1]] == [True, True]
    shown = texts(app)
    assert shown.index("First answer.") < shown.index("Second answer.")


def test_a_question_is_shown_as_text_never_as_markup(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "Is <b>oat milk</b> growing?")

    assert "Is &lt;b&gt;oat milk&lt;/b&gt; growing?" in bubbles(app)[0]
    assert "<b>oat milk</b>" not in bubbles(app)[0]


def test_the_sources_of_an_answer_fold_away_under_it(page):  # noqa: F811
    app = ask(page([AIMessage("A box costs 5.93 EUR [source](https://prepmymeal.com/boxen).")]),
              "What does Prepmymeal charge?")

    assert [fold.label for fold in app.expander if "source" in fold.label] == ["1 source"]


def test_an_answer_without_sources_has_no_folding_section_for_them(page):  # noqa: F811
    app = ask(page([AIMessage("An answer from what was said before.")]), "A question")

    assert [fold.label for fold in app.expander if "source" in fold.label] == []


def test_a_report_is_one_line_in_the_chat_with_a_way_to_open_it(page, tmp_path):  # noqa: F811
    app = with_a_report(page, tmp_path)

    assert "The report is ready: 0 sources, report check passed." in texts(app)
    # The report itself is in the Report view, not repeated in the chat.
    assert "Oat milk market value: 1 billion EUR" not in texts(app)

    button(app, "open_report_0").click().run()

    assert button(app, "view_report").proto.type == "secondary"
    assert "Oat milk market value: 1 billion EUR (Germany, 2025)." in texts(app)


# --- the question box and the suggestions ---------------------------------------------------------

def test_an_open_conversation_has_one_question_box(page):  # noqa: F811
    app = two_questions(page)

    assert len(app.chat_input) == 1
    assert app.chat_input[0].placeholder == "Ask a follow-up"


def test_three_next_questions_are_suggested(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "How big is the oat milk market?")

    assert suggestions(app) == ["Who are the main competitors?", "What do they charge?",
                                "Is demand rising?"]


def test_clicking_a_suggestion_asks_it(page):  # noqa: F811
    app = ask(page([AIMessage("First answer."), AIMessage("The answer about prices.")]),
              "How big is the oat milk market?")

    button(app, "suggest_1").click().run()

    assert not app.exception
    assert "What do they charge?" in bubbles(app)[1]
    assert "The answer about prices." in texts(app)


# --- the short reply for a report -----------------------------------------------------------------

def test_a_short_answer_is_its_own_reply_without_links_or_numbers():
    block = Block(role="assistant",
                  text="A box costs 5.93 EUR [source](https://prepmymeal.com/boxen). **Cheap** [[1]](https://x.example).")

    assert reply_summary(block) == "A box costs 5.93 EUR. Cheap."


def test_a_long_answer_is_cut_at_a_word_with_three_dots():
    reply = reply_summary(Block(role="assistant", text="word " * 100))

    assert len(reply) <= 221 and reply.endswith("word…")


def test_a_report_gets_a_line_saying_it_is_ready():
    passed = Block(role="assistant", report="# Market research report: oat milk", problems=[],
                   sources=[object()] * 11)
    with_problems = Block(role="assistant", report="# Market research report: oat milk",
                          problems=["a", "b"], sources=[object()])

    assert reply_summary(passed) == "The report is ready: 11 sources, report check passed."
    assert reply_summary(with_problems) == \
        "The report is ready: 1 source, the report check found 2 points."


def test_a_question_without_an_answer_says_so():
    assert reply_summary(None) == "No answer was written for this question."


# --- the steps under a question -------------------------------------------------------------------

def test_up_to_three_steps_are_listed_and_the_rest_counted():
    activity = ["Searched the web: a", "Workflow: Confirmed competitors: x", "Read the page b",
                "Searched the news: c", "Read the page d"]

    assert steps_for_thread(activity) == ["Searched the web: a", "Confirmed competitors: x",
                                          "Read the page b", "and 2 more steps"]


def test_three_steps_or_fewer_are_listed_in_full():
    assert steps_for_thread(["Read the page b"]) == ["Read the page b"]
    assert steps_for_thread([]) == []
    assert steps_for_thread(["a", "b", "c", "d"])[-1] == "and 1 more step"


def test_while_working_the_latest_steps_are_listed_and_the_earlier_ones_counted():
    steps = [f"step {number}" for number in range(1, 10)]

    assert steps_while_working(steps) == ["and 3 earlier steps", "step 4", "step 5", "step 6",
                                          "step 7", "step 8", "step 9"]
    assert steps_while_working(["step 1", "Workflow: step 2"]) == ["step 1", "step 2"]
