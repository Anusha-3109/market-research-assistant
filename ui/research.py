"""The research view.

A finished conversation has two panes. On the left is the page: the answer
to one question, with what it cost and the numbered list of sources it
cites. On the right is the chat panel: every question of the conversation
with its first steps and a short reply. Clicking a question puts its answer
on the page.

The same layout is used in two states:
- finished: drawn from the saved conversation (render_conversation);
- live: drawn while the agent is working, with a placeholder where the
  answer will go and the right-hand panels filling in (run_live).
"""

import itertools
import re
import time
from dataclasses import dataclass

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.agent import resume_steps, stream_steps
from agent.approval import Pause, Progress
from agent.config import MAX_QUESTION_CHARS
from agent.citations import Source, domain_of, titles_in_results
from agent.guards import friendly_error
from agent.pdf_export import report_to_pdf
from agent.report_check import format_check
from agent.session import (
    Turn,
    describe_tool_call,
    reply_summary,
    report_title,
    short_title,
    steps_for_thread,
    steps_while_working,
)
from agent.tools import safe_filename
from agent import usage
from agent.usage import Usage
from ui.approvals import render_pause
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
        return "Working on it. You can ask a follow-up when it is done."
    if waiting:
        return "Answer the question on the left to continue"
    return "Ask a follow-up" if has_turns else "Ask about a market"


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
        badge=fill("source_badge.html") if source.official else Html(""),
    )


def sources_html(sources: list[Source], empty: str) -> Html:
    if not sources:
        return fill("sources_empty.html", message=empty)
    return fill(
        "sources_panel.html",
        count=Html(f'<span class="gw-sources-count">{len(sources)}</span>'),
        rows=join(source_row(source) for source in sources),
    )


def sources_panel(sources: list[Source], empty: str = "No pages were cited.") -> None:
    """The numbered list of pages the answer cites."""
    with panel("sources_panel"):
        st.html(sources_html(sources, empty))


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
    count = plural(len(turns), "question")
    with st.container(key="conversation_bar", horizontal=True, vertical_alignment="center"):
        # The title was typed by a person: fill() shows it as text.
        st.html(fill("bar.html", title=short_title(turns[0].question, 60), count=count),
                width="stretch")
        new = st.button("New", key="bar_new", type="tertiary",
                        help="Start a new conversation. This one is kept.")
        close = st.button("", icon=":material/close:", key="bar_close", type="tertiary",
                          help="Close this conversation. It is kept in the list.")
    return new or close


def shown_turn(turns: list[Turn], thread_id: str, locked: bool) -> int:
    """The index of the turn whose answer is on the page. It is the newest,
    unless the user clicked an earlier question in the chat panel. A new
    answer, or an approval that is waiting, brings the page back to the
    newest."""
    latest = len(turns) - 1
    chosen = st.session_state.get("shown_turn")
    if locked or not chosen or chosen["thread"] != thread_id or chosen["turns"] != len(turns):
        return latest
    return min(chosen["index"], latest)


def _show_turn(thread_id: str, turns: int, index: int) -> None:
    st.session_state["shown_turn"] = {"thread": thread_id, "turns": turns, "index": index}


def thread_entries(turns: list[Turn], shown: int | None, thread_id: str,
                   waiting: bool = False, locked: bool = False, live: bool = False) -> None:
    """Every question of the conversation with its first steps and a short
    reply.

    shown:  the turn whose answer is on the page; its question is drawn
            filled. None while the agent is working on a new one.
    locked: the questions cannot be clicked (an approval is waiting, or
            the agent is working).
    live:   drawn by the live view. When a question is sent, the finished
            view and the live view are both drawn in the same run, and
            Streamlit allows a key only once per run; the live view's
            buttons therefore have keys of their own.
    """
    labels = tab_labels(turns, 60)
    latest = len(turns) - 1
    for index, turn in enumerate(turns):
        block = turn.answer
        # The question is a button: clicking it puts its answer on the page.
        st.button(short_title(turn.question, 90),
                  key=f"live_turn_{index}" if live else f"turn_{index}",
                  type="secondary" if index == shown else "tertiary",
                  help=f"Show: {labels[index]}", width="stretch", disabled=locked,
                  on_click=_show_turn, args=(thread_id, len(turns), index))
        used = usage.cost_text(block.usage) if block else ""
        count = len(block.sources) if block else 0
        meta = " · ".join(part for part in (used, plural(count, "source") if count else "") if part)
        # Steps and replies hold words from the web and from the model:
        # fill() shows them as text.
        st.html(fill(
            "thread_entry.html",
            steps=join(fill("thread_step.html", text=step)
                       for step in steps_for_thread(block.activity if block else [])),
            reply=reply_summary(block, waiting=waiting and index == latest),
            meta=meta))


def chat_panel(turns: list[Turn], shown: int, thread_id: str, waiting: Pause | None,
               box_text: str) -> tuple[bool, str | None]:
    """The panel beside the page: the bar, every question with its first
    steps and a short reply, and the question box at the bottom.

    Returns whether the bar's "New" or its cross was pressed, and the
    question that was typed, if any.
    """
    with st.container(key="chat_panel"):
        left = render_bar(turns)
        with st.container(key="chat_thread"):
            thread_entries(turns, shown, thread_id, waiting=waiting is not None,
                           locked=waiting is not None)
        typed = st.chat_input(box_text, key="question", submit_mode="disable",
                              disabled=waiting is not None, max_chars=MAX_QUESTION_CHARS)
    # Keep the newest entry of a long conversation in view.
    st.html(script_tag("thread_to_end.js"), unsafe_allow_javascript=True)
    return left, typed


def downloads(turn: Turn, index: int) -> None:
    """Download the answer as a Markdown file or a PDF. Both go to the
    user's own computer, so neither needs approval."""
    block = turn.answer
    content = block.report or block.text
    name = safe_filename(report_title(block.report) if block.report else turn.question)
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.download_button("Markdown", data=content, file_name=name, mime="text/markdown",
                           icon=":material/download:", key=f"download_md_{index}")
        st.download_button("PDF", data=report_to_pdf(content),
                           file_name=name.removesuffix(".md") + ".pdf",
                           mime="application/pdf", icon=":material/download:",
                           key=f"download_pdf_{index}")


def render_conversation(turns: list[Turn], thread_id: str, waiting: Pause | None,
                        box_text: str = "Ask a follow-up") -> Outcome:
    """Show a finished conversation: the page on the left, the chat panel
    on the right. box_text is what the empty question box says.

    If the agent is waiting for an approval, the form takes the place of
    the newest answer on the page.
    """
    outcome = Outcome()
    shown = shown_turn(turns, thread_id, locked=waiting is not None)
    is_latest = shown == len(turns) - 1
    page, panel_column = st.columns([1.75, 1], gap="medium")
    with page:
        _page(turns[shown], shown, thread_id, is_latest, waiting if is_latest else None, outcome)
    with panel_column:
        outcome.new, typed = chat_panel(turns, shown, thread_id, waiting, box_text)
        # A button on the page ("Save to reports folder") also asks a
        # question; what was typed comes first.
        outcome.question = typed or outcome.question
    # Hold the page at the top of the answer (see the script for why).
    st.html(script_tag("start_at_top.js"), unsafe_allow_javascript=True)
    return outcome


def _page(turn: Turn, index: int, thread_id: str, is_latest: bool,
          waiting: Pause | None, outcome: Outcome) -> None:
    """The page: one question's answer, what it took, and its sources."""
    block = turn.answer
    has_answer = block is not None and bool(block.report or block.text)
    elapsed = st.session_state.get("elapsed", {}).get(f"{thread_id}:{index}")
    steps = block.activity if block else []
    sources = block.sources if block else []

    with panel("answer_panel"):
        if waiting is not None:
            panel_heading(short_title(turn.question, 80), "WAITING FOR YOU")
            outcome.answer = render_pause(waiting)
        elif not has_answer:
            panel_heading(short_title(turn.question, 80), "QUESTION")
            st.caption("No answer was written for this question.")
        else:
            title = report_title(block.report) if block.report else short_title(turn.question, 80)
            panel_heading(title[:1].upper() + title[1:], "REPORT" if block.report else "ANSWER")
            if block.problems is not None:
                if block.problems:
                    st.warning(format_check(block.problems), title="Report check")
                else:
                    st.badge("Report check passed", icon=":material/check:", color="green")
            st.markdown(block.cited)
            if block.report or sources_cited(block):
                st.caption(DISCLAIMER)

    # Under the answer: what it took, the ways to keep it, and its sources.
    with st.container(key=f"page_foot_{next(_serial)}"):
        took_and_cost(len(steps), len(sources), elapsed,
                      used=block.usage if block else None,
                      used_is_partial=bool(block and block.usage_is_partial),
                      waiting=waiting is not None)
        if has_answer and waiting is None:
            if block.report or sources:
                downloads(turn, index)
            if block.report and is_latest and st.button(
                    "Save to reports folder", icon=":material/save:", key=f"save_{index}"):
                outcome.question = SAVE_QUESTION
    sources_panel(sources, empty="None yet." if waiting is not None
                  else "No pages were cited.")


def took_and_cost(step_count: int, source_count: int, elapsed: float | None,
                  used: Usage | None, used_is_partial: bool, waiting: bool) -> None:
    """One row under an answer: what it cost, in a pill, and a line with
    the steps, sources, tokens and time. The steps themselves are listed
    in the chat panel."""
    cost = usage.cost_text(used) if used else ""
    tokens = usage.tokens_text(used) if used else ""
    with st.container(horizontal=True, vertical_alignment="center"):
        if cost:
            # Pointing at the pill shows the figures behind it.
            st.html(fill("cost_pill.html", cost=cost, details=usage.details(used)), width="content")
        if waiting:
            parts = ["Waiting for you"]
        elif step_count:
            parts = [plural(step_count, "step"), plural(source_count, "source")]
        else:
            parts = ["Answered from this conversation, without a new search"]
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
             earlier_steps: list[str] | None = None, turns: list[Turn] | None = None) -> None:
    """Run the agent and show the research as it happens.

    Give `question` to start a new turn, or `answer` to continue after an
    approval form. `turns` is the conversation so far, for the chat panel.
    When the agent finishes or pauses, the caller redraws the page from
    the saved conversation.

    The layout is the same as the finished view. On the left a placeholder
    stands where the answer will be, with the pages found so far under it.
    On the right the chat panel shows the earlier questions, then this
    one with each step as it happens.
    """
    turns = turns or []
    # When an approval form was answered, the question is already the last
    # turn of the conversation.
    earlier = turns[:-1] if answer is not None and turns else turns

    page, panel_column = st.columns([1.75, 1], gap="medium")
    with page:
        with panel("answer_panel"):
            panel_heading(short_title(title, 80), "QUESTION")
            st.markdown(":shimmer[Writing the answer.] It appears here when it is ready.")
            st.html(load("skeleton.html"))
        sources_slot = st.empty()
    with panel_column:
        # These keys differ from the finished view's for the reason given
        # in thread_entries; the stylesheet matches both.
        with st.container(key="chat_panel_live"):
            with st.container(key="chat_thread_live"):
                thread_entries(earlier, None, thread_id, locked=True, live=True)
                st.button(short_title(title, 90), key=f"live_turn_{turn_index}", type="secondary",
                          width="stretch", disabled=True)
                steps_slot = st.empty()
            # Pressing any button makes Streamlit start the page again, which
            # ends this run. The page then tidies the half-finished turn
            # (app.py).
            st.button("Stop", icon=":material/stop_circle:", key=f"stop_{thread_id}_{turn_index}",
                      on_click=_mark_stopped, args=(thread_id,), width="stretch")
            st.chat_input("Working on it. You can ask a follow-up when it is done.",
                          key="question_while_working", disabled=True)
    st.html(script_tag("thread_to_end.js"), unsafe_allow_javascript=True)

    steps = [step.removeprefix("Workflow: ") for step in (earlier_steps or [])]
    found: dict[str, str] = {}         # address -> title, in the order found
    started = time.monotonic()

    def redraw() -> None:
        with steps_slot.container():
            st.html(fill("thread_working.html",
                         steps=join(fill("thread_step.html", text=step)
                                    for step in steps_while_working(steps)),
                         took=format_seconds(time.monotonic() - started)))
        with sources_slot.container():
            sources_panel([Source(number, page_title, domain_of(url), url)
                           for number, (url, page_title) in enumerate(found.items(), start=1)][:12],
                          empty="None yet.")

    def stay_with_message() -> None:
        """Keep an error on screen. Any button draws the page again from
        the saved conversation, where the question box works again."""
        st.button("Back to the conversation", key=f"back_{thread_id}_{turn_index}")
        st.stop()

    redraw()
    events = (stream_steps(agent, question, thread_id, context=context) if question
              else resume_steps(agent, answer, thread_id, context=context))
    try:
        for item in events:
            if isinstance(item, Progress):
                steps.append(item.text)
            elif isinstance(item, AIMessage):
                steps += [describe_tool_call(call["name"], call["args"])
                          for call in item.tool_calls]
            elif isinstance(item, ToolMessage):
                # Pages found by a search appear in the source list at once.
                for url, page_title in titles_in_results(str(item.content)).items():
                    found.setdefault(url, page_title)
            elif isinstance(item, Pause):
                pass                    # the caller shows the form after redrawing
            redraw()
    except GraphRecursionError:
        st.error("The assistant reached its step limit before finishing. "
                 "Try a narrower question.")
        stay_with_message()
    except Exception as error:          # model or network failure
        st.error(friendly_error(error), title="The assistant could not answer")
        stay_with_message()

    # Remember how long it took, for the "Done" panel.
    st.session_state.setdefault("elapsed", {})[f"{thread_id}:{turn_index}"] = (
        st.session_state.get("elapsed", {}).get(f"{thread_id}:{turn_index}", 0.0)
        + time.monotonic() - started)
