"""Tests for the two-pane view of a conversation: the answer as a page on
the left, and the conversation as a chat panel on the right.

The page is run without a browser, with a fake agent.
"""

from langchain_core.messages import AIMessage

from agent.session import Block, reply_summary, steps_for_thread, steps_while_working
from tests.test_app import button, page, texts  # noqa: F401  (page is a fixture)


def thread(app) -> str:
    """The HTML of the chat panel's entries."""
    return "\n".join(element.proto.body for element in app.get("html")
                     if 'class="gw-reply"' in element.proto.body)


def questions(app) -> list[str]:
    """The questions listed in the chat panel, oldest first."""
    return [b.label for b in app.button if (b.key or "").startswith("turn_")]


def ask(app, question: str):
    app.chat_input[0].set_value(question).run()
    return app


def two_questions(page):  # noqa: F811
    app = page([AIMessage("First answer."), AIMessage("Second answer.")])
    ask(app, "First question")
    return ask(app, "Second question")


# --- the chat panel -----------------------------------------------------------------------------

def test_the_chat_panel_lists_every_question_of_the_conversation(page):  # noqa: F811
    app = two_questions(page)

    assert not app.exception
    assert questions(app) == ["First question", "Second question"]


def test_the_newest_answer_is_the_page_and_each_question_has_a_short_reply(page):  # noqa: F811
    app = two_questions(page)

    # The page on the left holds the newest answer only.
    assert "Second answer." in texts(app) and "First answer." not in texts(app)
    # The panel on the right has a short reply for both.
    assert "First answer." in thread(app) and "Second answer." in thread(app)


def test_clicking_an_earlier_question_puts_its_answer_on_the_page(page):  # noqa: F811
    app = two_questions(page)

    button(app, "turn_0").click().run()

    assert "First answer." in texts(app) and "Second answer." not in texts(app)


def test_a_new_question_brings_the_page_back_to_the_newest_answer(page):  # noqa: F811
    app = page([AIMessage("First answer."), AIMessage("Second answer."), AIMessage("Third answer.")])
    ask(app, "First question")
    ask(app, "Second question")
    button(app, "turn_0").click().run()

    ask(app, "Third question")

    assert "Third answer." in texts(app) and "First answer." not in texts(app)


def test_the_question_on_the_page_is_marked_in_the_panel(page):  # noqa: F811
    app = two_questions(page)

    assert [button(app, key).proto.type for key in ("turn_0", "turn_1")] == ["tertiary", "secondary"]
    button(app, "turn_0").click().run()
    assert [button(app, key).proto.type for key in ("turn_0", "turn_1")] == ["secondary", "tertiary"]


def test_a_reply_in_the_panel_is_text_never_markup(page):  # noqa: F811
    app = ask(page([AIMessage("Use <script>alert(1)</script> with care.")]), "A question")

    assert "&lt;script&gt;" in thread(app)
    assert "<script>" not in thread(app)


# --- the short reply ---------------------------------------------------------------------------------

def test_a_short_answer_is_its_own_reply_without_links_or_numbers():
    block = Block(role="assistant",
                  text="A box costs 5.93 EUR [source](https://prepmymeal.com/boxen). **Cheap** [[1]](https://x.example).")

    assert reply_summary(block) == "A box costs 5.93 EUR. Cheap."


def test_a_long_answer_is_cut_at_a_word_with_three_dots():
    block = Block(role="assistant", text="word " * 100)

    reply = reply_summary(block)

    assert len(reply) <= 221 and reply.endswith("word…")


def test_a_report_gets_a_line_saying_it_is_ready():
    passed = Block(role="assistant", report="# Market research report: oat milk", problems=[],
                   sources=[object()] * 11)
    with_problems = Block(role="assistant", report="# Market research report: oat milk",
                          problems=["a", "b"], sources=[object()])

    assert reply_summary(passed) == \
        "The report is ready: 11 sources, report check passed. It is shown on the left."
    assert reply_summary(with_problems) == \
        "The report is ready: 1 source, the report check found 2 points. It is shown on the left."


def test_a_question_without_an_answer_and_one_that_is_waiting_say_so():
    assert reply_summary(None) == "No answer was written for this question."
    assert reply_summary(Block(role="assistant"), waiting=True) == \
        "Waiting for your decision, on the left."


# --- the steps under a question -------------------------------------------------------------------------

def test_up_to_three_steps_are_listed_and_the_rest_counted():
    activity = ["Searched the web: a", "Workflow: Confirmed competitors: x", "Read the page b",
                "Searched the news: c", "Read the page d"]

    assert steps_for_thread(activity) == ["Searched the web: a", "Confirmed competitors: x",
                                          "Read the page b", "and 2 more steps"]


def test_three_steps_or_fewer_are_listed_in_full():
    assert steps_for_thread(["Read the page b"]) == ["Read the page b"]
    assert steps_for_thread([]) == []
    assert steps_for_thread(["a", "b", "c", "d"])[-1] == "and 1 more step"


# --- the question box ----------------------------------------------------------------------------------

def in_order(block) -> list[str]:
    """The keys of the buttons and question boxes of a part of the page,
    from top to bottom."""
    seen = []
    for child in block.children.values():
        if hasattr(child, "children"):
            seen += in_order(child)
        elif child.type in ("button", "chat_input"):
            seen.append(child.key or "")
    return seen


def test_an_open_conversation_has_one_question_box_inside_the_chat_panel(page):  # noqa: F811
    app = two_questions(page)

    assert len(app.chat_input) == 1
    assert app.chat_input[0].placeholder == "Ask a follow-up"
    # It comes after the questions of the conversation, in the same panel.
    keys = in_order(app.main)
    assert keys.index("turn_1") < keys.index("question")
    assert keys.index("bar_new") < keys.index("question")


def test_the_start_screen_keeps_its_question_box(page):  # noqa: F811
    app = page()

    assert len(app.chat_input) == 1
    assert app.chat_input[0].placeholder == "Ask about a market"


def test_a_follow_up_typed_in_the_panel_is_answered(page):  # noqa: F811
    app = two_questions(page)

    assert questions(app) == ["First question", "Second question"]
    assert "Second answer." in texts(app)


# --- the steps while the agent is working -------------------------------------------------------------

def test_while_working_the_latest_steps_are_listed_and_the_earlier_ones_counted():
    steps = [f"step {number}" for number in range(1, 10)]

    assert steps_while_working(steps) == ["and 3 earlier steps", "step 4", "step 5", "step 6",
                                          "step 7", "step 8", "step 9"]


def test_a_few_steps_are_listed_in_full_while_working():
    assert steps_while_working(["step 1", "Workflow: step 2"]) == ["step 1", "step 2"]
    assert steps_while_working([]) == []
    assert steps_while_working([f"s{n}" for n in range(7)])[0] == "and 1 earlier step"
