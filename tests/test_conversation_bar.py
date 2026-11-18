"""Tests for the bar across the top of an open conversation: its title, how
many questions it holds, and the two buttons that leave it.

The page is run without a browser, with a fake agent.
"""

from langchain_core.messages import AIMessage

from tests.test_app import button, page  # noqa: F401  (page is a fixture)

START_TITLE = "Research **any market**."


def bar(app) -> str:
    """The HTML of the bar, or "" if there is none."""
    return "\n".join(element.proto.body for element in app.get("html")
                     if 'class="gw-bar-title"' in element.proto.body)


def address(app) -> str:
    value = app.query_params["c"]
    return value[0] if isinstance(value, list) else value


def ask(app, question: str):
    app.chat_input[0].set_value(question).run()
    return app


def test_the_start_screen_has_no_bar(page):  # noqa: F811
    app = page()

    assert bar(app) == ""
    assert "bar_new" not in [b.key for b in app.button]


def test_an_open_conversation_shows_its_title_and_one_question(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "How big is the oat milk market?")

    assert not app.exception
    assert "How big is the oat milk market?" in bar(app)
    assert "1 question<" in bar(app)                      # not "1 questions"


def test_the_bar_counts_the_questions_and_keeps_the_first_as_title(page):  # noqa: F811
    app = page([AIMessage("First answer."), AIMessage("Second answer.")])
    ask(app, "How big is the oat milk market?")

    ask(app, "Who are the competitors?")

    assert "How big is the oat milk market?" in bar(app)
    assert "2 questions<" in bar(app)


def test_a_title_is_shown_as_text_never_as_markup(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "Is <b>oat milk</b> growing?")

    assert "Is &lt;b&gt;oat milk&lt;/b&gt; growing?" in bar(app)
    assert "<b>oat milk</b>" not in bar(app)


def test_new_leaves_for_an_empty_conversation(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "How big is the oat milk market?")
    before = address(app)

    button(app, "bar_new").click().run()

    assert address(app) != before
    assert app.title[0].value == START_TITLE
    assert bar(app) == ""


def test_close_leaves_for_the_start_screen_too(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "How big is the oat milk market?")
    before = address(app)

    button(app, "bar_close").click().run()

    assert address(app) != before
    assert app.title[0].value == START_TITLE


def test_the_conversation_is_kept_after_leaving_it(page):  # noqa: F811
    app = ask(page([AIMessage("An answer.")]), "How big is the oat milk market?")

    button(app, "bar_close").click().run()

    listed = [b.label for b in app.sidebar.button if (b.key or "").startswith("open_")]
    assert listed == ["How big is the oat milk market?"]
