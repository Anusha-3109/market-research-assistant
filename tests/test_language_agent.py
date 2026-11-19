"""Tests for German answers and reports.

Three things follow the language switch here:
- the chat agent, the assistant and the report workflow are told to write
  in German;
- the fixed wording of a report (headings, table heads, "not found") is put
  into German when the report is shown or downloaded. The saved report
  itself is not changed, so everything that reads it keeps working;
- the one-pager and the slides are laid out with German headings.
"""

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agent.agent import assemble_agent, stream_steps
from agent.memory import UserContext
from agent.report.deps import Deps, in_language
from agent.report.formats import one_pager, slides
from agent.report.localize import localize, localize_phrase
from agent.report.render import render_report
from agent.report.snapshot import build_snapshot
from agent.side_assistant import ask
from tests.test_app import button, make_runtime, page  # noqa: F401  (page is a fixture)
from tests.test_assistant import RecordingModel
from tests.test_formats import SOURCES
from tests.test_language import switch
from tests.test_snapshot import final_state, with_snapshot
from tests.test_styles import listening


def report() -> str:
    return render_report(final_state())


# --- what the models are told --------------------------------------------------------------------

def told_in_chat(language: str | None) -> str:
    model = listening()
    agent = assemble_agent(model, [], tools=[], checkpointer=InMemorySaver(),
                           store=InMemoryStore(), extract_facts=lambda message: {})
    context = UserContext(user_id="tester", language=language)
    list(stream_steps(agent, "How big is HelloFresh?", "thread-1", context=context))
    return model.told()


def test_with_german_chosen_the_chat_agent_is_told_to_answer_in_german():
    told = told_in_chat("de")

    assert "Write your answer in German" in told
    assert 'formally, with "Sie"' in told
    assert "country names you pass to tools stay in English" in told


def test_in_english_the_chat_agent_hears_nothing_about_a_language():
    assert "German" not in told_in_chat("en")
    assert "German" not in told_in_chat(None)


def test_a_language_the_app_does_not_have_never_reaches_the_model():
    assert "Klingon" not in told_in_chat("Klingon") and "German" not in told_in_chat("Klingon")


def test_the_assistant_is_told_to_answer_in_german():
    model = RecordingModel("ok", "ok")

    ask(model, "Was ist CAGR?", history=[], context="", language="de")
    ask(model, "What is CAGR?", history=[], context="")

    assert "Write your answer in German" in model.sent[0][0].content
    assert "German" not in model.sent[1][0].content


def test_every_step_of_a_german_report_is_asked_to_write_in_german():
    heard = []
    deps = Deps(ask=lambda schema, instructions, material: heard.append(instructions),
                search=None, news=None, read_page=None, financials=None, trend=None)

    in_language(deps, "de").ask(dict, "List the competitors.", "material")
    in_language(deps, "en").ask(dict, "List the competitors.", "material")

    assert heard[0].startswith("List the competitors.")
    assert "Write every description, statement and analysis point in German" in heard[0]
    assert "in English" in heard[0]              # fields that ask for English stay English
    assert heard[1] == "List the competitors."


# --- a report shown in German --------------------------------------------------------------------

def test_the_fixed_wording_of_a_report_is_put_into_german():
    german = localize(report(), "de")

    assert german.startswith("# Marktforschungsbericht: oat milk in Germany")
    for heading in ("## 1. Marktüberblick", "## 2. Wettbewerber", "## 3. Preise", "## 4. Trends",
                    "## 5. SWOT-Analyse", "## 6. Quellen"):
        assert heading in german
    assert "| Unternehmen | Angebot | Größe oder Finanzzahlen | Quelle |" in german
    assert "| Unternehmen | Produkt oder Tarif | Preis | Quelle | Gefunden am |" in german
    assert "**Stärken:**" in german and "**Risiken:**" in german
    assert "Dieser Abschnitt ist die eigene Analyse des Assistenten" in german
    assert "nicht gefunden" in german and "not found" not in german


def test_what_the_research_found_is_left_as_it_is():
    english, german = report(), localize(report(), "de")

    assert "Oat milk market value: 1 billion EUR" in german          # a source's statement
    assert "Barista editions grow fastest" in german                  # a point of the SWOT
    assert german.count("https://") == english.count("https://")       # every link is still there


def test_in_english_a_report_is_not_touched():
    assert localize(report(), "en") == report()


def test_the_direction_of_a_trend_is_put_into_german():
    assert localize_phrase("rising (+32% from the first to the last quarter of the period)", "de") \
        == "steigend (+32% vom ersten zum letzten Quartal des Zeitraums)"
    assert localize_phrase("not found", "de") == "nicht gefunden"
    assert localize_phrase("not found", "en") == "not found"


# --- the other layouts ---------------------------------------------------------------------------

def test_the_one_pager_has_german_headings():
    page_text = one_pager("Oat milk in Germany", build_snapshot(final_state()), SOURCES, language="de")

    for heading in ("## Kennzahlen", "## Wettbewerber", "## Nachfrage", "## Chancen", "## Risiken",
                    "## Quellen"):
        assert heading in page_text
    assert "Investoren-Einseiter · 2 Quellen" in page_text
    assert "- Bestätigte Wettbewerber: **2** von 5 Kandidaten" in page_text
    assert "Preis: nicht gefunden." in page_text


def test_the_slides_have_german_titles():
    deck = slides("Oat milk in Germany", build_snapshot(final_state()), SOURCES, language="de")

    assert [slide.title for slide in deck] == [
        "Oat milk in Germany", "Der Markt", "Wettbewerber", "Preise", "Nachfrage",
        "Chancen und Risiken", "Quellen"]
    assert deck[0].bullets == ["Marktforschung · 2 Quellen"]
    assert deck[3].bullets[1] == "Alpro: nicht gefunden"
    assert deck[5].bullets[0] == "Chance: Barista editions grow fastest"


# --- on the page ---------------------------------------------------------------------------------

def german(app):
    switch(app).set_value("de").run()
    assert not app.exception
    return app


def html(app) -> str:
    return "\n".join(element.proto.body for element in app.get("html"))


def test_the_report_view_shows_the_report_in_german(page, tmp_path):  # noqa: F811
    app = german(with_snapshot(page, tmp_path, report=report()))
    button(app, "view_report").click().run()

    shown = html(app)
    assert '<span class="gw-section-title">1. Marktüberblick</span>' in shown
    assert "1 nicht gefunden" in shown or "2 nicht gefunden" in shown      # a status tag
    downloaded = next(b for b in app.get("download_button") if b.label == "Markdown").proto
    assert downloaded.label == "Markdown"


def test_the_ask_view_says_in_german_that_the_report_is_ready(page, tmp_path):  # noqa: F811
    app = german(with_snapshot(page, tmp_path))
    button(app, "view_ask").click().run()

    assert "Der Bericht ist fertig: 0 Quellen, Berichtsprüfung bestanden." in \
        [m.value for m in app.markdown]


def test_the_language_chosen_on_the_page_reaches_the_model(page, tmp_path):  # noqa: F811
    model = listening()
    app = german(page(runtime=make_runtime(tmp_path, [], model=model)))

    app.chat_input[0].set_value("How big is HelloFresh?").run()

    assert "Write your answer in German" in model.told()


# --- found in a real German report ---------------------------------------------------------------

def test_the_reason_a_price_is_missing_is_put_into_german_as_a_whole():
    row = "| Mølk | not found | not found (the company's own website was not found) | x |"

    assert localize(row, "de") == ("| Mølk | nicht gefunden | nicht gefunden (die eigene Website "
                                   "des Unternehmens wurde nicht gefunden) | x |")


def test_the_labels_of_a_companys_figures_are_put_into_german():
    line = "Revenue (last 12 months): 945.3 million USD; Market value: 233.3 million USD; Employees: 1392"

    assert localize_phrase(line, "de") ==         "Umsatz (letzte 12 Monate): 945.3 million USD; Marktwert: 233.3 million USD; Beschäftigte: 1392"


def test_the_size_of_a_company_holds_its_figures_only():
    state = final_state()
    state["profiles"][0].figures = "\n".join([
        "Source used: Yahoo Finance", "Company: Oatly Group AB (ticker OTLY)",
        "Revenue: 783 million USD", "Employees: not found"])

    assert build_snapshot(state)["competitors"][0]["size"] == "Revenue: 783 million USD"
