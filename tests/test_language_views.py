"""Tests for the German Ask and Report views: with DE chosen, the words the
app itself writes in these views are German.

A choice keeps its value: the format of a report is still "Investor
one-pager" underneath, whatever the picker shows.
"""

from tests.test_app import button, page  # noqa: F401  (page is a fixture)
from tests.test_formats import format_picker
from tests.test_language import switch
from tests.test_snapshot import with_snapshot


def german(app):
    switch(app).set_value("de").run()
    assert not app.exception
    return app


def html(app) -> str:
    return "\n".join(element.proto.body for element in app.get("html"))


def captions(app) -> list[str]:
    return [c.value for c in app.caption]


def ask_view(page, tmp_path):  # noqa: F811
    app = german(with_snapshot(page, tmp_path))
    button(app, "view_ask").click().run()
    assert not app.exception
    return app


def report_view(page, tmp_path):  # noqa: F811
    app = german(with_snapshot(page, tmp_path))
    button(app, "view_report").click().run()
    assert not app.exception
    return app


# --- the Ask view --------------------------------------------------------------------------------

def test_the_bar_and_the_question_box_are_in_german(page, tmp_path):  # noqa: F811
    app = ask_view(page, tmp_path)

    assert '<span class="gw-bar-chip">1 Frage</span>' in html(app)
    assert button(app, "bar_new").label == "Neu"
    assert app.chat_input[0].placeholder == "Stellen Sie eine Anschlussfrage"


def test_an_answer_without_a_search_says_so_in_german(page, tmp_path):  # noqa: F811
    from langchain_core.messages import AIMessage

    app = german(page([AIMessage("Eine Antwort.")]))
    app.chat_input[0].set_value("Was ist CAGR?").run()

    assert any("Aus dieser Unterhaltung beantwortet, ohne neue Suche" in line
               for line in captions(app))


def test_the_report_line_and_the_cost_row_are_in_german(page, tmp_path):  # noqa: F811
    app = ask_view(page, tmp_path)

    assert button(app, "open_report_0").label == "Bericht öffnen"
    assert any("1 Schritt · 0 Quellen" in line for line in captions(app))
    assert '>LLM-Kosten <b>' not in html(app)            # the fake model reports no cost


def test_the_suggestions_are_german_questions(page, tmp_path):  # noqa: F811
    app = ask_view(page, tmp_path)

    assert [b.label for b in app.button if (b.key or "").startswith("suggest_")] == \
        ["Wer sind die wichtigsten Wettbewerber?", "Was verlangen sie?", "Steigt die Nachfrage?"]


def test_in_english_the_ask_view_reads_as_before(page, tmp_path):  # noqa: F811
    app = with_snapshot(page, tmp_path)
    button(app, "view_ask").click().run()

    assert '<span class="gw-bar-chip">1 question</span>' in html(app)
    assert app.chat_input[0].placeholder == "Ask a follow-up"
    assert button(app, "open_report_0").label == "Open report"


# --- the Report view -----------------------------------------------------------------------------

def test_the_report_view_is_in_german(page, tmp_path):  # noqa: F811
    app = report_view(page, tmp_path)

    shown = html(app)
    assert '<div class="gw-view-kicker">Bericht</div>' in shown
    assert '<div class="gw-contents-label">Inhalt</div>' in shown
    assert "<span>Quellen</span>" in shown and "Es wurden keine Seiten zitiert." in shown
    assert button(app, "save_0").label == "Im Berichtsordner speichern"
    assert "Recherche-Zusammenfassung aus öffentlichen Quellen, keine Anlageberatung." in captions(app)


def test_the_formats_have_german_names_but_keep_their_values(page, tmp_path):  # noqa: F811
    app = report_view(page, tmp_path)

    picker = next(box for box in app.selectbox if box.key == "report_format")
    assert picker.label == "Format"
    assert picker.options == ["Vollständiger Marktbericht", "Investoren-Einseiter",
                              "Pitch-Deck-Folien"]
    assert picker.value == "Full market report"


def test_choosing_a_format_in_german_shows_that_layout(page, tmp_path):  # noqa: F811
    app = report_view(page, tmp_path)

    next(box for box in app.selectbox if box.key == "report_format") \
        .set_value("Pitch deck slides").run()

    assert not app.exception
    assert html(app).count('class="gw-slide-title"') == 6      # this report cites no sources
    assert [b.label for b in app.get("download_button")] == ["PowerPoint"]


def test_in_english_the_format_picker_reads_as_before(page, tmp_path):  # noqa: F811
    app = with_snapshot(page, tmp_path)
    button(app, "view_report").click().run()

    assert format_picker(app).options == ["Full market report", "Investor one-pager",
                                          "Pitch deck slides"]
    assert button(app, "save_0").label == "Save to reports folder"
