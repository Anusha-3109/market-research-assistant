"""Tests for the German frame of the app: with DE chosen, the sidebar, the
names of the views, the Snapshot and the assistant panel are in German.

What a person chose or what the research found is not translated: a
setting keeps its stored value, and a figure keeps its source's wording.
"""

from agent import config
from tests.test_app import button, page  # noqa: F401  (page is a fixture)
from tests.test_assistant import helper, helper_box  # noqa: F401  (helper is a fixture)
from tests.test_language import switch
from tests.test_snapshot import build_snapshot, final_state, snapshot_html, view_links, with_snapshot
from tests.test_snapshot_tabs import CITED, shown_in
from ui.texts import counted, t
from ui.words import en


def german(app):
    switch(app).set_value("de").run()
    assert not app.exception
    return app


# --- texts that count ------------------------------------------------------------------------------

def test_a_counted_text_has_a_form_for_one_and_a_form_for_more():
    assert counted("snapshot.of_candidates", 1, language="en") == "of 1 candidate"
    assert counted("snapshot.of_candidates", 5, language="en") == "of 5 candidates"
    assert counted("snapshot.of_candidates", 1, language="de") == "von 1 Kandidat"
    assert counted("snapshot.of_candidates", 5, language="de") == "von 5 Kandidaten"


def test_the_english_style_descriptions_are_the_ones_the_agent_is_given():
    assert {name: en.TEXTS[f"style.about.{name}"] for name in config.STYLE_CHOICES} == \
        dict(config.STYLE_CHOICES)


def test_every_choice_of_a_setting_has_a_name_in_both_languages():
    for language in ("en", "de"):
        for name in config.STYLE_CHOICES:
            assert t(f"style.{name}", language=language)
        for name in config.LENGTH_CHOICES:
            assert t(f"length.{name}", language=language)
        for key in config.PROFILE_KEYS:
            assert t(f"profile.{key}", language=language)


# --- the sidebar ---------------------------------------------------------------------------------

def test_the_sidebar_is_in_german(page):  # noqa: F811
    app = german(page())

    assert button(app, "new_conversation").label == "Neue Unterhaltung"
    assert [e.label for e in app.sidebar.expander] == ["Einstellungen", "Hilfe"]
    captions = [c.value for c in app.sidebar.caption]
    assert "Marktforschung vor dem Start" in captions
    assert "Unterhaltungen" in captions and "Was ich mir merke" in captions


def test_the_views_have_german_names(page, tmp_path):  # noqa: F811
    app = german(with_snapshot(page, tmp_path))

    assert view_links(app) == ["Überblick", "Fragen", "Bericht"]
    assert "Unterhaltung" in [c.value for c in app.sidebar.caption]       # above the picker


def test_a_setting_is_named_in_german_but_keeps_its_value(page):  # noqa: F811
    app = german(page())

    style = next(box for box in app.sidebar.selectbox if box.key == "set_style")
    assert style.label == "Antwortstil"
    assert style.options == ["Ausgewogen", "Förmlich", "Freundlich", "Knapp"]
    assert style.value == "Balanced"                       # what is saved and sent to the agent
    length = next(s for s in app.sidebar.select_slider if s.key == "set_length")
    assert length.options == ["Kurz", "Mittel", "Lang", "Keine Grenze"]
    assert length.value == "No limit"


def test_choosing_a_style_in_german_saves_the_same_value_as_in_english(page):  # noqa: F811
    app = german(page())

    next(box for box in app.sidebar.selectbox if box.key == "set_style").set_value("Concise").run()

    assert not app.exception
    assert app.session_state["set_style"] == "Concise"
    assert "Die kürzeste nützliche Antwort, ohne Einleitung und Schlusswort" in \
        [c.value for c in app.sidebar.caption]


# --- the Snapshot --------------------------------------------------------------------------------

def test_the_snapshot_is_in_german(page, tmp_path):  # noqa: F811
    app = german(with_snapshot(page, tmp_path, report=CITED))

    assert [tab.label for tab in app.tabs] == ["Übersicht", "Wettbewerber", "Preise", "Trends", "SWOT"]
    shown = snapshot_html(app)
    assert "Überblick aus 2 Quellen erstellt" in shown
    assert "Bestätigte Wettbewerber" in shown and "von 5 Kandidaten" in shown
    assert button(app, "snapshot_report").label == "Bericht öffnen"
    assert button(app, "snapshot_ask").label == "Anschlussfrage stellen"


def test_the_tables_and_the_swot_have_german_headings(page, tmp_path):  # noqa: F811
    app = german(with_snapshot(page, tmp_path))

    assert "<th>Wettbewerber</th><th>Angebot</th><th>Größe oder Finanzzahlen</th>" in \
        shown_in(app, "Wettbewerber")
    assert "<th>Wettbewerber</th><th>Ein Preis</th>" in shown_in(app, "Preise")
    assert 'Suchinteresse für „Hafermilch“' in shown_in(app, "Trends")
    swot = shown_in(app, "SWOT")
    heads = [part.split("<")[0] for part in swot.split('class="gw-snap-head">')[1:]]
    assert heads == ["Stärken", "Schwächen", "Chancen", "Risiken"]


def test_what_the_research_found_is_not_translated(page, tmp_path):  # noqa: F811
    app = german(with_snapshot(page, tmp_path))

    assert "Oat milk market value" in shown_in(app, "Übersicht")          # the source's wording
    assert "<td>Alpro</td><td>nicht gefunden</td>" in shown_in(app, "Preise")


def test_an_empty_tab_says_so_in_german(page, tmp_path):  # noqa: F811
    snapshot = build_snapshot(final_state())
    snapshot.update(competitors=[], trend=None, opportunities=[], strengths=[], weaknesses=[],
                    threats=[])

    app = german(with_snapshot(page, tmp_path, snapshot=snapshot))

    assert "Für diesen Bericht wurden keine Wettbewerber bestätigt." in shown_in(app, "Wettbewerber")
    assert "Für diesen Bericht wurde kein Nachfragetrend gemessen." in shown_in(app, "Trends")
    assert "Der Bericht hat keinen SWOT-Abschnitt." in shown_in(app, "SWOT")


def test_in_english_the_snapshot_reads_as_before(page, tmp_path):  # noqa: F811
    app = with_snapshot(page, tmp_path, report=CITED)

    assert [tab.label for tab in app.tabs] == ["Overview", "Competitors", "Pricing", "Trends", "SWOT"]
    assert "Snapshot generated from 2 sources" in snapshot_html(app)
    assert 'Search interest for "Hafermilch"' in shown_in(app, "Trends").replace("&quot;", '"')


# --- the assistant -------------------------------------------------------------------------------

def test_the_assistant_panel_is_in_german(page, tmp_path, helper):  # noqa: F811
    app = german(with_snapshot(page, tmp_path))
    assert button(app, "assistant_open").label == "Assistent"

    button(app, "assistant_open").click().run()

    assert helper_box(app).placeholder == "Fragen Sie etwas zu diesem Bericht…"
    head = next(e.proto.body for e in app.get("html") if 'class="gw-helper-head"' in e.proto.body)
    assert "Assistent · Oat milk in Germany" in head and "Nur zu dieser Unterhaltung" in head
    assert button(app, "assistant_new").label == "Neuer Chat"
    assert "Wird nicht zur Unterhaltung hinzugefügt" in [c.value for c in app.caption]
