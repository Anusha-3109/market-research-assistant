"""The research view.

One question is shown at a time. On the left is the answer; on the right is
how it was researched (the steps and the time taken) and the numbered list
of sources the answer cites. Earlier questions in the conversation are
reachable as tabs across the top.

The same layout is used in two states:
- finished: drawn from the saved conversation (render_turn);
- live: drawn while the agent is working, with a placeholder where the
  answer will go and the right-hand panels filling in (run_live).
"""

import itertools
import re
import time
from dataclasses import dataclass
from html import escape

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.agent import resume_steps, stream_steps
from agent.approval import Pause, Progress
from agent.citations import Source, domain_of, titles_in_results
from agent.guards import friendly_error
from agent.pdf_export import report_to_pdf
from agent.report_check import format_check
from agent.session import Turn, describe_tool_call, report_title, short_title
from agent.tools import safe_filename
from ui.approvals import render_pause

SAVE_QUESTION = "Save this report."
STEPS_SHOWN = 6
DISCLAIMER = "Research summary from public sources, not investment advice."

# Streamlit allows a key only once per run, and the live view redraws its
# panels many times in one run. Each panel therefore gets a numbered key;
# the CSS matches on the part before the number.
_serial = itertools.count()


def panel(name: str):
    return st.container(key=f"{name}_{next(_serial)}")


# Grey bars standing in for the answer while it is being written.
SKELETON = (
    '<div class="gw-skeleton"><div style="width:100%"></div><div style="width:93%"></div>'
    '<div style="width:86%"></div><div style="width:62%"></div></div>'
)


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

def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds:.1f}s" if seconds < 10 else f"{seconds:.0f}s"


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def steps_panel(title: str, steps: list[str], elapsed: float | None, source_count: int) -> None:
    """The panel listing what the agent did."""
    with panel("steps_panel"):
        took = format_seconds(elapsed)
        st.markdown(f"**{title}**" + (f" :gray[· {took}]" if took else ""))

        if title == "Done":
            st.caption(":material/check_circle: " + (
                f"{plural(len(steps), 'step')} · {plural(source_count, 'source')}" if steps
                else "Answered from this conversation, without a new search"))
        for step in steps[-STEPS_SHOWN:] if title != "Done" else steps[:STEPS_SHOWN]:
            st.caption(f":material/search: {step}")
        hidden = len(steps) - STEPS_SHOWN
        if hidden > 0 and title == "Done":
            with st.expander(f"{hidden} more steps", type="compact"):
                for step in steps[STEPS_SHOWN:]:
                    st.caption(f":material/search: {step}")
        elif hidden > 0:
            st.caption(f"and {hidden} earlier steps")


SAFE_DOMAIN = re.compile(r"[a-z0-9.-]+")


def source_row(source: Source) -> str:
    """One source as HTML: number, site icon, title, site name, badge.

    Titles and addresses come from the web, so both are escaped. The icon
    is the site's own favicon; where a site has none, the letter tile
    underneath it stays visible.
    """
    url = escape(source.url, quote=True)
    domain = escape(source.domain, quote=True)
    letter = escape(source.domain[:1].upper())
    badge = '<span class="gw-official">Official</span>' if source.official else ""
    # Drawn as a background, so a site without an icon shows nothing here
    # (an <img> would show a broken-picture mark) and the letter remains.
    icon = (f'<span class="gw-source-favicon" '
            f'style="background-image:url(https://{domain}/favicon.ico)"></span>'
            if SAFE_DOMAIN.fullmatch(source.domain) else "")
    return (
        f'<a class="gw-source" href="{url}" target="_blank" rel="noopener noreferrer" '
        f'title="{escape(source.title, quote=True)}">'
        f'<span class="gw-source-number">{source.number}</span>'
        f'<span class="gw-source-icon">{letter}'
        f'{icon}</span>'
        f'<span class="gw-source-text">'
        f'<span class="gw-source-title">{escape(source.title)}</span>'
        f'<span class="gw-source-site"><code>{domain}</code>{badge}</span>'
        f'</span></a>'
    )


def sources_html(sources: list[Source], empty: str) -> str:
    rows = "".join(source_row(source) for source in sources)
    count = f'<span class="gw-sources-count">{len(sources)}</span>' if sources else ""
    body = (f'<div class="gw-sources-list">{rows}</div>' if sources
            else f'<div class="gw-sources-empty">{escape(empty)}</div>')
    return f'<div class="gw-sources-head"><span>Sources</span>{count}</div>{body}'


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


# Streamlit keeps a page with a question box scrolled to the bottom. An
# answer should be read from its top, so this script holds the page there
# until the reader scrolls or clicks for themselves.
START_AT_TOP = """
<script>
(() => {
    const area = document.querySelector('[data-testid="stAppScrollToBottomContainer"]');
    if (!area) return;
    let readerActed = false;
    for (const event of ['wheel', 'touchstart', 'keydown', 'mousedown']) {
        window.addEventListener(event, () => { readerActed = true; },
                                {once: true, passive: true});
    }
    const hold = () => { if (!readerActed && area.scrollTop > 4) area.scrollTop = 0; };
    area.addEventListener('scroll', hold);
    [0, 100, 400, 900].forEach(delay => setTimeout(hold, delay));
})();
</script>
"""


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


def render_tabs(turns: list[Turn], thread_id: str, locked: bool) -> int:
    """The questions of this conversation as tabs. Returns the index of the
    one to show. The newest is selected when a new answer arrives."""
    latest = len(turns) - 1
    if locked or len(turns) == 1:
        # One tab, or an approval is waiting on the newest: nothing to choose.
        labels = tab_labels(turns, 46)
        st.pills("Questions", [latest], default=latest, key=f"tab_{thread_id}_{latest}_fixed",
                 format_func=labels.__getitem__,
                 label_visibility="collapsed", disabled=locked and len(turns) > 1)
        return latest

    # The key changes with the number of turns, so a new answer resets the
    # selection to the newest tab.
    labels = tab_labels(turns, 34)
    chosen = st.pills("Questions", list(range(len(turns))), default=latest,
                      key=f"tab_{thread_id}_{len(turns)}",
                      format_func=labels.__getitem__,
                      label_visibility="collapsed")
    return latest if chosen is None else chosen


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


def render_turn(turn: Turn, index: int, thread_id: str, is_latest: bool,
                waiting: Pause | None) -> Outcome:
    """Show one question with its answer, steps and sources.

    If the agent is waiting for an approval on this turn, the form takes
    the place of the answer.
    """
    outcome = Outcome()
    block = turn.answer
    has_answer = block is not None and bool(block.report or block.text)
    elapsed = st.session_state.get("elapsed", {}).get(f"{thread_id}:{index}")

    left, right = st.columns([1.9, 1], gap="medium")

    with left:
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

    with right:
        steps = block.activity if block else []
        sources = block.sources if block else []
        steps_panel("Waiting for you" if waiting is not None else "Done",
                    [step.removeprefix("Workflow: ") for step in steps], elapsed, len(sources))
        sources_panel(sources, empty="None yet." if waiting is not None
                      else "No pages were cited.")

        if has_answer and waiting is None:
            if block.report or sources:
                downloads(turn, index)
            if block.report and is_latest and st.button(
                    "Save to reports folder", icon=":material/save:", key=f"save_{index}",
                    width="stretch"):
                outcome.question = SAVE_QUESTION
        if st.button("Research another market", key=f"another_{index}", width="stretch"):
            outcome.new = True
    st.html(START_AT_TOP, unsafe_allow_javascript=True)
    return outcome


# --- the live view --------------------------------------------------------------------------------

def _mark_stopped(thread_id: str) -> None:
    st.session_state["stopped"] = thread_id


def run_live(agent, thread_id: str, context, title: str, turn_index: int,
             question: str | None = None, answer: dict | None = None,
             earlier_steps: list[str] | None = None) -> None:
    """Run the agent and show the research as it happens.

    Give `question` to start a new turn, or `answer` to continue after an
    approval form. When the agent finishes or pauses, the caller redraws
    the page from the saved conversation.
    """
    tab, stop = st.columns([5, 1], vertical_alignment="center")
    tab.pills("Questions", ["now"], default="now", key=f"tab_live_{thread_id}_{turn_index}",
              format_func=lambda _: f":material/progress_activity: {short_title(title, 46)}",
              label_visibility="collapsed", disabled=True)
    # Pressing any button makes Streamlit start the page again, which ends
    # this run. The page then tidies the half-finished turn (app.py).
    stop.button("Stop", icon=":material/stop_circle:", key=f"stop_{thread_id}_{turn_index}",
                on_click=_mark_stopped, args=(thread_id,), width="stretch")

    left, right = st.columns([1.9, 1], gap="medium")
    with left:
        with panel("answer_panel"):
            panel_heading(short_title(title, 80), "QUESTION")
            st.markdown(":shimmer[Writing the answer.] It appears here when it is ready.")
            st.html(SKELETON)
    with right:
        steps_slot = st.empty()
        sources_slot = st.empty()

    steps = [step.removeprefix("Workflow: ") for step in (earlier_steps or [])]
    found: dict[str, str] = {}         # address -> title, in the order found
    started = time.monotonic()

    def redraw() -> None:
        with steps_slot.container():
            steps_panel("Researching", steps, time.monotonic() - started, len(found))
        with sources_slot.container():
            sources_panel([Source(number, page_title, domain_of(url), url)
                           for number, (url, page_title) in enumerate(found.items(), start=1)][:12],
                          empty="None yet.")

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
        st.stop()                       # keep the message on screen
    except Exception as error:          # model or network failure
        st.error(friendly_error(error), title="The assistant could not answer")
        st.stop()

    # Remember how long it took, for the "Done" panel.
    st.session_state.setdefault("elapsed", {})[f"{thread_id}:{turn_index}"] = (
        st.session_state.get("elapsed", {}).get(f"{thread_id}:{turn_index}", 0.0)
        + time.monotonic() - started)
