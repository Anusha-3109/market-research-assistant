"""The views of an open conversation.

- Ask: the conversation as one full-width chat. Every question is followed
  by the steps taken and its answer. A report is one line there, with a
  button that opens it.
- Report: the newest report on its own, with what it cost and its sources.

The Ask view is drawn in two states:
- finished: from the saved conversation (render_ask_view);
- live: while the agent is working, with the steps of the new question
  appearing one by one (run_live).
"""

import itertools
import re
import time
from dataclasses import dataclass
from uuid import uuid4

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.agent import resume_steps, stream_steps
from agent.approval import Pause, Progress
from agent.citations import Source, domain_of, titles_in_results
from agent.config import APP_NAME
from agent.guards import friendly_error
from agent.pdf_export import report_to_pdf
from agent.report_check import format_check
from agent.session import (
    Turn,
    describe_tool_call,
    reply_summary,
    report_sections,
    section_counts,
    report_title,
    short_title,
    steps_for_thread,
    steps_while_working,
)
from agent.pptx_export import slides_to_pptx
from agent.report.formats import FULL, ONE_PAGER, SLIDES, one_pager, slides
from agent.report.snapshot import trend_bars
from agent.tools import safe_filename
from agent import usage
from agent.usage import Usage
from ui.approvals import render_pause
from agent.report.localize import localize, localize_phrase
from ui.texts import counted, current_language, t
from ui.assets import Html, fill, join, load, script_tag

SAVE_QUESTION = "Save this report."
DISCLAIMER = "Research summary from public sources, not investment advice."

# Streamlit allows a key only once per run, and the live view redraws its
# panels many times in one run. Each panel therefore gets a numbered key;
# the CSS matches on the part before the number.
_serial = itertools.count()


def panel(name: str):
    return st.container(key=f"{name}_{next(_serial)}")


@dataclass
class Outcome:
    """What the user did in the view, if anything.

    question: a question to send (a button that asks one was pressed).
    answer:   the answer to an approval form that was submitted.
    new:      True if "Research another market" was pressed.
    """

    question: str | None = None
    answer: dict | None = None
    new: bool = False


# --- pieces shared by the finished and the live view ------------------------------------------

def question_box_text(resuming: bool, waiting: bool, has_turns: bool) -> str:
    """What the empty question box at the bottom of the page says.

    resuming:  an approval form was just submitted and the agent is
               carrying on.
    waiting:   the agent is stopped until an approval form is answered.
    has_turns: the conversation already has a question in it.
    """
    if resuming:
        return t("ask.box_working")
    if waiting:
        return t("ask.box_waiting")
    return t("ask.box_follow_up") if has_turns else t("ask.box_first")


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds:.1f}s" if seconds < 10 else f"{seconds:.0f}s"


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


SAFE_DOMAIN = re.compile(r"[a-z0-9.-]+")


def source_row(source: Source) -> Html:
    """One source as HTML: number, site icon, title, site name, badge.

    The markup is in ui/static/source_row.html. Titles and addresses come
    from the web; fill() escapes them. The icon is the site's own favicon,
    drawn as a background so that a site without one shows the letter tile
    underneath (an <img> would show a broken-picture mark).
    """
    has_icon = bool(SAFE_DOMAIN.fullmatch(source.domain))
    return fill(
        "source_row.html",
        url=source.url, title=source.title, number=source.number,
        domain=source.domain, letter=source.domain[:1].upper(),
        icon=fill("source_icon.html", domain=source.domain) if has_icon else Html(""),
        badge=fill("source_badge.html", word=t("sources.official")) if source.official else Html(""),
    )


def sources_html(sources: list[Source], empty: str) -> Html:
    if not sources:
        return fill("sources_empty.html", title=t("sources.title"), message=empty)
    return fill(
        "sources_panel.html", title=t("sources.title"),
        count=Html(f'<span class="gw-sources-count">{len(sources)}</span>'),
        rows=join(source_row(source) for source in sources),
    )


def sources_panel(sources: list[Source], empty: str | None = None) -> None:
    """The numbered list of pages the answer cites."""
    with panel("sources_panel"):
        st.html(sources_html(sources, t("sources.none") if empty is None else empty))


def sources_cited(block) -> bool:
    return bool(block and block.sources)


def panel_heading(title: str, kind: str) -> None:
    st.subheader(title, anchor=False)
    st.caption(kind)
    st.divider()


# --- the finished view --------------------------------------------------------------------------

def tab_labels(turns: list[Turn], limit: int) -> list[str]:
    """One label per turn: the report's title if the answer is a report,
    otherwise the question.

    The labels must all differ. Streamlit tells tabs apart by their text,
    so two tabs reading the same would open the same answer. A repeated
    label gets a number: "Meal kits in Germany (2)".
    """
    labels: list[str] = []
    for turn in turns:
        report = turn.answer.report if turn.answer else ""
        base = short_title(report_title(report) if report else turn.question, limit)
        label, copy = base, 2
        while label in labels:
            label, copy = f"{base} ({copy})", copy + 1
        labels.append(label)
    return labels


def render_bar(turns: list[Turn]) -> bool:
    """The bar across the top of an open conversation: its title (the first
    question), how many questions it holds, and two buttons that leave it.
    Returns True if one of them was pressed.

    "New" and the cross both lead to an empty conversation; this one stays
    in the list in the sidebar.
    """
    count = counted("ask.questions", len(turns))
    with st.container(key="conversation_bar", horizontal=True, vertical_alignment="center"):
        # The title was typed by a person: fill() shows it as text.
        st.html(fill("bar.html", title=short_title(turns[0].question, 60), count=count),
                width="stretch")
        new = st.button(t("ask.new"), key="bar_new", type="tertiary", help=t("ask.new_help"))
        close = st.button("", icon=":material/close:", key="bar_close", type="tertiary",
                          help=t("ask.close_help"))
    return new or close


def downloads(turn: Turn, index: int, content: str | None = None, suffix: str = "") -> None:
    """Download the answer as a Markdown file or a PDF. Both go to the
    user's own computer, so neither needs approval.

    content: another layout of the report to download in its place.
    suffix:  added to the file name for that layout, such as "one-pager".
    """
    block = turn.answer
    # A report is downloaded in the language it is shown in.
    content = content or localize(block.report, current_language()) or block.text
    name = safe_filename(report_title(block.report) if block.report else turn.question)
    if suffix:
        name = name.removesuffix(".md") + f"-{suffix}.md"
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.download_button("Markdown", data=content, file_name=name, mime="text/markdown",
                           icon=":material/download:", key=f"download_md_{index}")
        st.download_button("PDF", data=report_to_pdf(content),
                           file_name=name.removesuffix(".md") + ".pdf",
                           mime="application/pdf", icon=":material/download:",
                           key=f"download_pdf_{index}")


# Offered under the chat. They lean on the conversation so far, so "they"
# and "demand" mean the market that is being talked about.
SUGGESTIONS = ["ask.suggest.0", "ask.suggest.1", "ask.suggest.2"]


def _open_report(thread_id: str) -> None:
    st.session_state["view"] = {"thread": thread_id, "name": "report"}


def question_bubble(question: str) -> None:
    # The question was typed by a person: fill() shows it as text.
    st.html(fill("ask_question.html", question=question))


def answer_head() -> None:
    """The assistant's robot face and name at the top of an answer."""
    st.html(fill("answer_head.html", app=APP_NAME))


def summary_line(block) -> str:
    """One or two lines about an answer, for the chat. For a report the
    line is the app's own wording, so it follows the language."""
    if block is None or not block.report:
        return t("ask.no_answer") if block is None or not block.text else reply_summary(block)
    sources = counted("ask.sources", len(block.sources))
    if block.problems is None:
        return t("ask.ready", sources=sources)
    if not block.problems:
        return t("ask.ready_passed", sources=sources)
    return t("ask.ready_points", sources=sources, points=len(block.problems))


def steps_above_answer(activity: list[str]) -> None:
    steps = steps_for_thread(activity)
    if steps:
        # Steps hold words from the web: fill() shows them as text.
        st.html(fill("ask_steps.html", steps=join(fill("thread_step.html", text=step)
                                                 for step in steps)))


def render_ask_view(turns: list[Turn], thread_id: str, waiting: Pause | None,
                    rate=None) -> Outcome:
    """Show a finished conversation as a chat: the bar, every question with
    its steps and its answer, then suggestions for a next question.

    If the agent is waiting for an approval, its form takes the place of
    the newest answer. The question box itself is drawn by the page, which
    keeps it at the bottom of the window. `rate(index, turn)`, when given,
    draws the thumbs under an answer (ui/feedback.py).
    """
    outcome = Outcome()
    outcome.new = render_bar(turns)
    latest = len(turns) - 1
    with st.container(key="ask_thread"):
        for index, turn in enumerate(turns):
            question_bubble(turn.question)
            _answer(turn, index, thread_id, waiting if index == latest else None, outcome, rate)

    if waiting is None:
        with st.container(key="ask_suggestions", horizontal=True):
            for number, suggestion in enumerate(t(name) for name in SUGGESTIONS):
                if st.button(suggestion, key=f"suggest_{number}"):
                    outcome.question = suggestion
    return outcome


def _answer(turn: Turn, index: int, thread_id: str, waiting: Pause | None,
            outcome: Outcome, rate=None) -> None:
    """One answer in the chat, under its question."""
    block = turn.answer
    with panel("answer_panel"):
        answer_head()
        steps_above_answer(block.activity if block else [])
        if waiting is not None:
            outcome.answer = render_pause(waiting)
            return
        if block is None or not (block.report or block.text):
            st.caption(t("ask.no_answer"))
            return
        if block.report:
            # The report is in the Report view; here it is one line.
            st.markdown(summary_line(block))
            st.button(t("ask.open_report"), icon=":material/description:", key=f"open_report_{index}",
                      type="primary", on_click=_open_report, args=(thread_id,))
        else:
            st.markdown(block.cited)
            if sources_cited(block):
                st.caption(t("disclaimer"))

    elapsed = st.session_state.get("elapsed", {}).get(f"{thread_id}:{index}")
    with st.container(key=f"page_foot_{next(_serial)}"):
        took_and_cost(len(block.activity), len(block.sources), elapsed, used=block.usage,
                      used_is_partial=block.usage_is_partial, waiting=False)
        if rate is not None:
            rate(index, turn)
        if not block.report:
            if block.sources:
                with st.expander(counted("ask.sources", len(block.sources)), type="compact"):
                    st.html(sources_html(block.sources, empty=""))
            downloads(turn, index)


def render_report_view(turns: list[Turn], thread_id: str, rate=None) -> Outcome:
    """Show the newest report of a conversation: the Report view.

    On the left each section of the report is a card with its title and a
    status. On the right a box lists the contents, says what the report
    cost, and holds the buttons that download or save it. The sources are
    listed under the cards.
    """
    outcome = Outcome()
    index = max(number for number, turn in enumerate(turns)
                if turn.answer is not None and turn.answer.report)
    turn = turns[index]
    block = turn.answer
    title = report_title(block.report)
    title = title[:1].upper() + title[1:]
    language = current_language()
    # The saved report is English; its fixed wording follows the language.
    intro, sections = report_sections(localize(block.cited, language))

    # The heading is plain text from the report: fill() shows it as text.
    st.html(fill("ask_head.html", kicker=t("view.report"), title=title))
    cards, side = st.columns([2.1, 1], gap="medium")
    # The side is drawn first in the code, because the format chosen there
    # decides what the cards show. On the page it still sits on the right.
    with side:
        with st.container(key="report_side"):
            # Other layouts are made from the figures kept with the report,
            # so a report without them has the full report only.
            layout = FULL
            if block.snapshot:
                # A format is shown by its name in the chosen language; the
                # choice itself stays the same in every language.
                layout = st.selectbox(
                    t("report.format"), [FULL, ONE_PAGER, SLIDES], key="report_format",
                    format_func=lambda name: t(f"format.{name}", language=language),
                    help=t("report.format_help"))
            page = one_pager(title, block.snapshot, block.sources, language) \
                if layout == ONE_PAGER else None
            deck = slides(title, block.snapshot, block.sources, language) \
                if layout == SLIDES else None
            if page is None and deck is None:
                st.html(fill("contents.html", label=t("report.contents"), title=title,
                             items=join(fill("contents_item.html", title=section.title)
                                        for section in sections)))
            elapsed = st.session_state.get("elapsed", {}).get(f"{thread_id}:{index}")
            took_and_cost(len(block.activity), len(block.sources), elapsed, used=block.usage,
                          used_is_partial=block.usage_is_partial, waiting=False)
            if rate is not None:
                rate(index, turn)
            if deck is not None:
                name = safe_filename(report_title(block.report)).removesuffix(".md")
                st.download_button(
                    "PowerPoint", data=slides_to_pptx(deck), file_name=f"{name}-slides.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    icon=":material/download:", key=f"download_pptx_{index}", width="stretch")
            else:
                downloads(turn, index, content=page, suffix="one-pager" if page else "")
            if index == len(turns) - 1 and st.button(
                    t("report.save"), icon=":material/save:", key=f"save_{index}",
                    type="primary", width="stretch"):
                outcome.question = SAVE_QUESTION
    with cards:
        if deck is not None:
            _slides_on_the_page(deck)
            st.caption(t("disclaimer"))
        elif page is not None:
            # One page: everything after its title line, which the heading
            # of the view already shows.
            with panel("one_pager"):
                st.markdown(page.split("\n", 1)[1])
            st.caption(t("disclaimer"))
        else:
            if block.problems is not None:
                if block.problems:
                    st.warning(format_check(block.problems), title=t("report.check"))
                else:
                    st.badge(t("report.check_passed"), icon=":material/check:", color="green")
            if intro:
                st.caption(intro)
            for section in sections:
                status = section_counts(section.body)
                tag = Html("")
                if status:
                    kind, count = status
                    tag = fill("section_tag.html", kind=kind,
                               text=t("report.not_found", count=count) if kind == "warn"
                               else counted("ask.sources", count))
                with panel("report_section"):
                    st.html(fill("section_head.html", title=section.title, tag=tag))
                    st.markdown(section.body)
            st.caption(t("disclaimer"))
            sources_panel(block.sources)
    st.html(script_tag("start_at_top.js"), unsafe_allow_javascript=True)
    return outcome


def _open_view(thread_id: str, name: str) -> None:
    st.session_state["view"] = {"thread": thread_id, "name": name}


def _is_web_address(url: str) -> bool:
    return url.startswith(("https://", "http://"))


SNAPSHOT_TABS = ["overview", "competitors", "pricing", "trends", "swot"]
# The boxes of the SWOT tab, by the names their lines are kept under.
SWOT_PARTS = ["strengths", "weaknesses", "opportunities", "threats"]


def render_snapshot_view(turns: list[Turn], thread_id: str) -> Outcome:
    """Show the key figures of the newest report at a glance: the Snapshot
    view. Everything shown was kept by the report workflow as a separate
    value (agent/report/snapshot.py); nothing is worked out here.

    The words come from the web and from the model, so every one of them
    goes through fill(), which shows it as text.
    """
    block = next(turn.answer for turn in reversed(turns)
                 if turn.answer is not None and turn.answer.report)
    snapshot = block.snapshot
    title = report_title(block.report)

    head, action = st.columns([4, 1], vertical_alignment="bottom")
    head.html(fill("ask_head.html", kicker=t("view.snapshot"),
                   title=title[:1].upper() + title[1:]))
    with action.container(key="snapshot_actions"):
        st.button(t("snapshot.open_report"), icon=":material/description:", key="snapshot_report",
                  type="primary", width="stretch", on_click=_open_view,
                  args=(thread_id, "report"))

    if block.sources:
        st.html(fill("snap_from.html", text=counted("snapshot.from", len(block.sources))))

    with st.container(key="snapshot_tabs"):
        overview, competitors, pricing, trends, swot = st.tabs(
            [t(f"snapshot.tab.{name}") for name in SNAPSHOT_TABS])
    rows = snapshot["competitors"]
    with overview:
        _figure_tiles(snapshot)
    with competitors:
        if rows:
            st.html(fill("snap_table.html", competitor=t("snapshot.col.competitor"),
                         offer=t("snapshot.col.offer"), size=t("snapshot.col.size"), rows=join(
                fill("snap_row.html", company=row["name"], offer=row["offer"],
                     size=localize_phrase(row["size"], current_language()))
                for row in rows)))
        else:
            st.html(fill("snap_empty.html", head=t("snapshot.tab.competitors"),
                         text=t("snapshot.no_competitors")))
    with pricing:
        if rows:
            # What was not found is said, not left out.
            st.html(fill("snap_prices.html", competitor=t("snapshot.col.competitor"),
                         price=t("snapshot.col.price"), rows=join(
                fill("snap_price_row.html", company=row["name"],
                     price=localize_phrase(row["price"], current_language()),
                     # Why no price was found; a snapshot saved before the
                     # reason was kept has none.
                     note=fill("snap_price_note.html",
                               text=localize(row["price_note"], current_language()))
                     if row.get("price_note") else Html(""))
                for row in rows)))
        else:
            st.html(fill("snap_empty.html", head=t("snapshot.tab.pricing"),
                         text=t("snapshot.no_prices")))
    with trends:
        _trend_chart(snapshot["trend"])
    with swot:
        _swot_boxes(snapshot)

    with st.container(key="snapshot_ask_row"):
        st.button(t("snapshot.ask"), icon=":material/chat_bubble:", key="snapshot_ask",
                  type="tertiary", on_click=_open_view, args=(thread_id, "ask"))
    st.html(script_tag("start_at_top.js"), unsafe_allow_javascript=True)
    return Outcome()


def _figure_tiles(snapshot: dict) -> None:
    """The key figures as cards, and how many competitors were confirmed."""
    tiles = [fill("snap_tile.html", label=figure["label"], value=figure["value"],
                  note=figure["note"],
                  source=fill("snap_source.html", url=figure["url"], word=t("snapshot.source"))
                  if _is_web_address(figure["url"]) else Html(""),
                  # A snapshot saved before conversion existed has no such value.
                  converted=fill("snap_converted.html", text=figure["converted"])
                  if figure.get("converted") else Html(""))
             for figure in snapshot["figures"]]
    tiles.append(fill("snap_tile.html", label=t("snapshot.confirmed"),
                      value=snapshot["confirmed"],
                      note=counted("snapshot.of_candidates", snapshot["candidates"]), source=Html(""),
                      converted=Html("")))
    st.html(fill("snap_tiles.html", tiles=join(tiles)))


def _swot_boxes(snapshot: dict) -> None:
    """The SWOT as up to four boxes. A part that was not kept, or that is
    empty, gets no box: a snapshot saved before all four parts were kept
    shows the parts it has."""
    boxes = [fill("snap_list.html", head=t(f"swot.{part}"), items=join(
                 fill("snap_item.html", text=text) for text in snapshot.get(part) or []))
             for part in SWOT_PARTS if snapshot.get(part)]
    if boxes:
        st.html(fill("snap_swot.html", boxes=join(boxes)))
    else:
        st.html(fill("snap_empty.html", head=t("snapshot.swot"), text=t("snapshot.no_swot")))


def _trend_chart(trend: dict | None) -> None:
    """The demand trend as bars. The tallest bars are drawn stronger, so
    the peak stands out."""
    bars = trend_bars(trend["points"]) if trend else []
    if not bars:
        st.html(fill("snap_empty.html", head=t("snapshot.trend"), text=t("snapshot.no_trend")))
        return
    top = max(value for _, value in bars) or 1
    direction = localize_phrase(trend["direction"], current_language()) \
        or t("snapshot.measured")
    if not trend["reliable"]:
        direction += t("snapshot.caution")
    st.html(fill(
        "snap_chart.html", head=t("snapshot.trend_for", term=trend["term"]), direction=direction,
        first=bars[0][0], last=bars[-1][0],
        bars=join(fill("snap_bar.html", height=max(3, round(value / top * 100)),
                       high=Html(" gw-snap-bar-high") if value >= 0.85 * top else Html(""))
                  for _, value in bars)))


def _slides_on_the_page(deck: list) -> None:
    """The pitch deck as cards, two to a row. Every word goes through
    fill(), which shows it as text: the lines come from the web."""
    cards = []
    for number, slide in enumerate(deck, start=1):
        chart = Html("")
        if slide.bars:
            top = max(value for _, value in slide.bars) or 1
            chart = fill("slide_chart.html", bars=join(
                fill("snap_bar.html", height=max(3, round(value / top * 100)),
                     high=Html(" gw-snap-bar-high") if value >= 0.85 * top else Html(""))
                for _, value in slide.bars))
        cards.append(fill("slide.html", title=slide.title, number=number, chart=chart,
                          first=Html(" gw-slide-first" if number == 1
                                     else " gw-slide-plain" if slide.numbered else ""),
                          lines=join(fill("slide_line.html", text=bullet)
                                     for bullet in slide.bullets)))
    st.html(fill("slides.html", slides=join(cards)))


def took_and_cost(step_count: int, source_count: int, elapsed: float | None,
                  used: Usage | None, used_is_partial: bool, waiting: bool) -> None:
    """One row under an answer: what it cost, in a pill, and a line with
    the steps, sources, tokens and time. The steps themselves are listed
    in the chat panel."""
    cost = usage.cost_text(used) if used else ""
    tokens = t("cost.tokens", count=f"{used.total_tokens:,}") if used and used.calls else ""
    with st.container(horizontal=True, vertical_alignment="center"):
        if cost:
            # Pointing at the pill shows the figures behind it.
            st.html(fill("cost_pill.html", label=t("cost.label"), cost=cost,
                         details=usage.details(used)), width="content")
        if waiting:
            parts = [t("cost.waiting")]
        elif step_count:
            parts = [counted("cost.steps", step_count), counted("ask.sources", source_count)]
        else:
            parts = [t("cost.from_conversation")]
        took = format_seconds(elapsed)
        parts += [part for part in (tokens, took) if part]
        st.caption(":material/check_circle: " + " · ".join(parts))
    missing = usage.cost_note(used, partial=used_is_partial) if used else ""
    if missing:
        st.caption(f":material/info: {missing}")


# --- the live view --------------------------------------------------------------------------------

def _mark_stopped(thread_id: str) -> None:
    st.session_state["stopped"] = thread_id


def run_live(agent, thread_id: str, context, title: str, turn_index: int,
             question: str | None = None, answer: dict | None = None,
             earlier_steps: list[str] | None = None, turns: list[Turn] | None = None,
             on_error=None) -> dict:
    """Run the agent and show the research as it happens.

    Give `question` to start a new turn, or `answer` to continue after an
    approval form. `turns` is the conversation so far. When the agent
    finishes or pauses, the caller redraws the page from the saved
    conversation.

    The chat shows the earlier questions, each with a short line for its
    answer, then this question with every step as it happens, a placeholder
    where the answer will be, and the pages found so far.
    """
    turns = turns or []
    # When an approval form was answered, the question is already the last
    # turn of the conversation.
    earlier = turns[:-1] if answer is not None and turns else turns

    with st.container(key="ask_thread_live"):
        for turn in earlier:
            question_bubble(turn.question)
            # A short line only: the finished view, drawn earlier in this
            # same run, already used the keys of the full answers.
            st.caption(summary_line(turn.answer))
        question_bubble(title)
        steps_slot = st.empty()
        with panel("answer_panel"):
            answer_head()
            st.markdown(t("live.writing"))
            st.html(load("skeleton.html"))
        sources_slot = st.empty()
        # Pressing any button makes Streamlit start the page again, which
        # ends this run. The page then tidies the half-finished turn
        # (app.py).
        st.button(t("live.stop"), icon=":material/stop_circle:", key=f"stop_{thread_id}_{turn_index}",
                  on_click=_mark_stopped, args=(thread_id,))

    steps = [step.removeprefix("Workflow: ") for step in (earlier_steps or [])]
    # The tools of this turn, also those before an approval pause.
    used_tools = st.session_state.setdefault("turn_tools", {}).setdefault(
        f"{thread_id}:{turn_index}", [])
    found: dict[str, str] = {}         # address -> title, in the order found
    started = time.monotonic()

    def redraw() -> None:
        with steps_slot.container():
            st.html(fill("thread_working.html", word=t("live.researching"),
                         steps=join(fill("thread_step.html", text=step)
                                    for step in steps_while_working(steps)),
                         took=format_seconds(time.monotonic() - started)))
        if found:
            with sources_slot.container():
                sources_panel([Source(number, page_title, domain_of(url), url)
                               for number, (url, page_title)
                               in enumerate(found.items(), start=1)][:12])

    def stay_with_message() -> None:
        """Keep an error on screen. Any button draws the page again from
        the saved conversation, where the question box works again."""
        st.button(t("live.back"), key=f"back_{thread_id}_{turn_index}")
        st.stop()

    redraw()
    # The run's id in LangSmith, so a rating of this answer can reach its
    # trace (agent/trace_feedback.py).
    run_id = str(uuid4())
    events = (stream_steps(agent, question, thread_id, context=context, run_id=run_id) if question
              else resume_steps(agent, answer, thread_id, context=context, run_id=run_id))
    try:
        for item in events:
            if isinstance(item, Progress):
                steps.append(item.text)
            elif isinstance(item, AIMessage):
                steps += [describe_tool_call(call["name"], call["args"])
                          for call in item.tool_calls]
                used_tools.extend(call["name"] for call in item.tool_calls)
            elif isinstance(item, ToolMessage):
                # Pages found by a search appear in the source list at once.
                for url, page_title in titles_in_results(str(item.content)).items():
                    found.setdefault(url, page_title)
            elif isinstance(item, Pause):
                pass                    # the caller shows the form after redrawing
            redraw()
    except GraphRecursionError:
        if on_error:
            on_error(list(used_tools), time.monotonic() - started, t("live.step_limit", language="en"))
        st.error(t("live.step_limit"))
        stay_with_message()
    except Exception as error:          # model or network failure
        if on_error:
            on_error(list(used_tools), time.monotonic() - started, friendly_error(error))
        st.error(friendly_error(error), title=t("live.failed"))
        stay_with_message()

    # Remember how long it took, for the "Done" panel.
    st.session_state.setdefault("elapsed", {})[f"{thread_id}:{turn_index}"] = (
        st.session_state.get("elapsed", {}).get(f"{thread_id}:{turn_index}", 0.0)
        + time.monotonic() - started)
    return {"tools": list(used_tools),
            "seconds": st.session_state["elapsed"][f"{thread_id}:{turn_index}"],
            "run_id": run_id, "index": turn_index}
