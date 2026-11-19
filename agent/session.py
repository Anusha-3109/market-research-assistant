"""What a user interface needs to show conversations.

Nothing here imports Streamlit, so it can be tested without a browser and
reused by any interface.

- turn the saved messages of a conversation into simple blocks to display;
- list the saved conversations with a title each;
- with accounts on, keep track of which account a conversation belongs to.
"""

import re
import uuid
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.store.base import BaseStore

from agent.citations import Source, number_citations, titles_in_results, without_references
from agent.config import REPORT_HEADING
from agent.memory import DEFAULT_USER, forget_profile, load_profile, save_preference
from agent.report.tool import REPORT_TOOL_NAME
from agent.usage import BACKGROUND_KEY, Usage, total, usage_of

TITLE_MAX_CHARS = 42
MAX_CONVERSATIONS = 20


def new_thread_id() -> str:
    """A short random id for a new conversation."""
    return uuid.uuid4().hex[:8]


# --- what the agent did, in plain words ---------------------------------------------------

def describe_tool_call(name: str, args: dict) -> str:
    """One line describing a tool call for a person who has never heard of
    tools: 'Searched the web: meal kits Germany'."""
    if name == "web_search":
        return f"Searched the web: {args.get('query', '')}"
    if name == "search_news":
        return f"Searched the news: {args.get('query', '')}"
    if name == "read_webpage":
        return f"Read the page {args.get('url', '')}"
    if name == "get_demand_trend":
        return f"Checked search interest for '{args.get('term', '')}' in {args.get('country', '')}"
    if name == "get_company_financials":
        return f"Looked up company figures for {args.get('company', '')}"
    if name == REPORT_TOOL_NAME:
        return f"Started a report on {args.get('product', '')} in {args.get('country', '')}"
    if name == "save_report":
        # The tool call is only a request: the user approves it before any
        # file is written, and may change the title or decline.
        return f"Asked to save the report as '{args.get('title', '')}'"
    if name == "remember_preference":
        return f"Remembered your {str(args.get('key', '')).replace('_', ' ')}"
    if name == "forget_preferences":
        return "Cleared what was remembered about you"
    return f"Used {name}"


# --- messages -> blocks to display ----------------------------------------------------------

@dataclass
class Block:
    """One message in the conversation, prepared for display.

    role:     "user" or "assistant".
    text:     the words as stored (empty when the block is only a report).
    report:   a full report in markdown, as stored, if there is one.
    problems: the report check's findings; None if no check was run.
    activity: what the agent did to produce this block, one line each.

    For the research view, the same content with numbered citations:
    cited:    the text or report with each link turned into [1], [2] ...
    sources:  the pages those numbers refer to.
    """

    role: str
    text: str = ""
    report: str = ""
    problems: list[str] | None = None
    activity: list[str] = field(default_factory=list)
    cited: str = ""
    sources: list[Source] = field(default_factory=list)
    # The tokens and cost of every model call made to produce this block.
    usage: Usage = field(default_factory=Usage)
    # True for a report written before costs were recorded: the workflow's
    # own calls are missing from the figures.
    usage_is_partial: bool = False
    # The key figures of a report as separate values (agent/report/snapshot.py).
    # None for an answer that is not a report, or a report saved before
    # snapshots existed.
    snapshot: dict | None = None


def to_blocks(messages: list) -> list[Block]:
    """Turn a conversation's saved messages into blocks for display.

    Each user message is one block. Everything the agent did until the next
    user message is gathered into one assistant block: its tool calls become
    the activity list, and its answer or report becomes the content.
    """
    blocks: list[Block] = []
    current: Block | None = None
    # Collected while reading one answer, used to name and mark its sources.
    question = ""
    titles: dict[str, str] = {}
    official: set[str] = set()
    # What the background call that read the user's message used. It is
    # shown with the answer to that message.
    background = Usage()

    def assistant() -> Block:
        nonlocal current, background
        if current is None:
            current = Block(role="assistant", usage=background)
            background = Usage()
            blocks.append(current)
        return current

    def finish() -> None:
        """Number the citations of the answer that has just ended."""
        if current is None:
            return
        shown = without_references(current.report) if current.report else current.text
        # A report knows which sites are the companies' own. For a plain
        # answer, a site named in the question is taken to be official.
        current.cited, current.sources = number_citations(
            shown, titles, official, subject="" if current.report else question)

    for message in messages:
        content = message.content if isinstance(message.content, str) else ""

        if isinstance(message, HumanMessage):
            finish()
            if background.calls and blocks:
                # The question before this one never got an answer (it was
                # stopped). What its background call used was still paid
                # for, so it stays with that question and in the total.
                blocks[-1].usage += background
            blocks.append(Block(role="user", text=content))
            current, question, titles, official = None, content, {}, set()
            noted = message.response_metadata.get(BACKGROUND_KEY)
            background = total([noted] if noted else [])

        elif isinstance(message, AIMessage):
            block = assistant()
            block.usage += usage_of(message)
            for call in message.tool_calls:
                block.activity.append(describe_tool_call(call["name"], call["args"]))
            if content.strip():
                block.text = (block.text + "\n\n" + content).strip()

        elif isinstance(message, ToolMessage) and message.name == REPORT_TOOL_NAME:
            # The report tool's result is shown as it is: it is either a
            # full report or a short message (a question, a cancellation).
            block = assistant()
            details = getattr(message, "artifact", None) or {}
            if REPORT_HEADING in content:
                block.report = content
                block.problems = details.get("problems")
            else:
                block.text = (block.text + "\n\n" + content).strip()
            block.activity += [f"Workflow: {line}" for line in details.get("log", [])]
            if "usage" in details:
                block.usage += total([details["usage"]])
            elif block.report:
                block.usage_is_partial = True
            titles.update(details.get("titles", {}))
            official.update(details.get("official", []))
            if block.report:
                block.snapshot = details.get("snapshot")

        elif isinstance(message, ToolMessage):
            # Search results carry the titles of the pages they found.
            titles.update(titles_in_results(content))

    finish()
    if background.calls and blocks:
        blocks[-1].usage += background      # the last question was stopped unanswered
    return blocks


@dataclass
class Turn:
    """One question with its answer. The research view shows one turn at a
    time."""

    question: str
    answer: Block | None      # None while the answer has not been written


def to_turns(blocks: list[Block]) -> list[Turn]:
    """Pair each user message with the assistant block that follows it."""
    turns: list[Turn] = []
    for block in blocks:
        if block.role == "user":
            turns.append(Turn(question=block.text, answer=None))
        elif turns and turns[-1].answer is None:
            turns[-1].answer = block
    return turns


# --- the chat panel: a few lines about each turn ---------------------------------------
#
# In the chat (the Ask view) a report is one short line, because the report
# itself is in the Report view. While the agent works, earlier answers are
# shown as short lines too.

REPLY_MAX_CHARS = 220
STEPS_IN_THREAD = 3

_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")       # [words](address)
_CITATION = re.compile(r"\[\[\d+\]\]\([^)]*\)")    # [[1]](address)
_NUMBER = re.compile(r"^\[?\d+\]?$")                # the words of a citation: 1 or [1]


def _plain(text: str) -> str:
    """Markdown as plain words: links keep their words, a link that is only
    a citation ("source", or a number) goes, and marks for bold and
    headings are dropped."""
    def words_of(link: re.Match) -> str:
        words = link.group(1).strip()
        return "" if words.lower() == "source" or _NUMBER.match(words) else words

    text = _CITATION.sub("", text)
    text = _LINK.sub(words_of, text)
    text = re.sub(r"[*`#]", "", text)
    text = " ".join(text.split())
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


def reply_summary(block: "Block | None") -> str:
    """One or two lines about an answer, for the chat."""
    if block is None or not (block.report or block.text):
        return "No answer was written for this question."
    if block.report:
        count = len(block.sources)
        sources = f"{count} source" if count == 1 else f"{count} sources"
        if block.problems is None:
            check = ""
        elif not block.problems:
            check = ", report check passed"
        else:
            points = len(block.problems)
            check = f", the report check found {points} point" + ("" if points == 1 else "s")
        return f"The report is ready: {sources}{check}."

    text = _plain(block.text)
    if len(text) <= REPLY_MAX_CHARS:
        return text
    # Cut at the last whole word that fits.
    return text[:REPLY_MAX_CHARS].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def steps_for_thread(activity: list[str]) -> list[str]:
    """The first few steps of a turn, and a count of the rest."""
    steps = [step.removeprefix("Workflow: ") for step in activity]
    hidden = len(steps) - STEPS_IN_THREAD
    if hidden <= 0:
        return steps
    return steps[:STEPS_IN_THREAD] + [f"and {hidden} more step" + ("" if hidden == 1 else "s")]


# --- the Report view: a report as sections ---------------------------------------------
#
# A report is one text in markdown. The Report view shows each of its
# sections as a card, so the text is split at the section headings ("## ").

@dataclass
class Section:
    title: str      # "2. Competitors"
    body: str       # the markdown under the heading


def report_sections(report: str) -> tuple[str, list[Section]]:
    """Split a report into the text before its first section and its
    sections. The report's own title line ("# ...") is left out: the view
    shows the title itself."""
    intro: list[str] = []
    sections: list[Section] = []
    for line in report.splitlines():
        if line.startswith("## "):
            sections.append(Section(line[3:].strip(), ""))
        elif sections:
            sections[-1].body += line + "\n"
        elif not line.startswith("# "):
            intro.append(line)
    for section in sections:
        section.body = section.body.strip()
    return "\n".join(intro).strip(), sections


_SOURCE_NUMBER = re.compile(r"\[\[(\d+)\]\]")


def section_status(body: str) -> tuple[str, str] | None:
    """A short status for a section, with its kind ("ok" or "warn").

    Only what can be counted in the text is reported: how many values the
    research could not find, or else how many different sources the
    section cites. A section with neither has no status.
    """
    counted = section_counts(body)
    if counted is None:
        return None
    kind, count = counted
    if kind == "warn":
        return f"{count} not found", "warn"
    return (f"{count} source" if count == 1 else f"{count} sources"), "ok"


def section_counts(body: str) -> tuple[str, int] | None:
    """What section_status counts, as a number: ("warn", values not found)
    or ("ok", sources cited). The section may be shown in German."""
    missing = len(re.findall(r"not found|nicht gefunden", body, flags=re.IGNORECASE))
    if missing:
        return "warn", missing
    sources = len(set(_SOURCE_NUMBER.findall(body)))
    return ("ok", sources) if sources else None


STEPS_WHILE_WORKING = 6


def steps_while_working(steps: list[str]) -> list[str]:
    """The latest steps of a turn that is still running, with a count of
    the earlier ones in front."""
    steps = [step.removeprefix("Workflow: ") for step in steps]
    hidden = len(steps) - STEPS_WHILE_WORKING
    if hidden <= 0:
        return steps
    return [f"and {hidden} earlier step" + ("" if hidden == 1 else "s")] + steps[hidden:]


def short_title(text: str, limit: int = TITLE_MAX_CHARS) -> str:
    """One line, cut to a limit, for a tab or a heading."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


# --- the list of conversations ------------------------------------------------------------------

@dataclass
class Conversation:
    thread_id: str
    title: str


def report_title(report: str) -> str:
    """The title of a report for a file name: its heading without the
    fixed "Market research report:" part."""
    for line in report.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            return title.removeprefix("Market research report:").strip() or title
    return "Market research report"


def title_from(messages: list) -> str:
    """A conversation's title: its first user message, shortened."""
    for message in messages:
        if isinstance(message, HumanMessage) and isinstance(message.content, str):
            text = " ".join(message.content.split())
            if len(text) > TITLE_MAX_CHARS:
                text = text[:TITLE_MAX_CHARS].rstrip() + "…"
            return text or "Untitled"
    return ""


def thread_ids(checkpointer) -> list[str]:
    """The ids of all saved conversations, most recently used first.

    The checkpointer saves a row after every step. One query for the newest
    row of each conversation is much faster than loading them all. Rows
    belonging to the report workflow (which saves its own progress under a
    sub-name) are left out.
    """
    checkpointer.setup()    # creates the table in a brand-new memory file
    rows = checkpointer.conn.execute(
        "SELECT thread_id, MAX(rowid) AS newest FROM checkpoints "
        "WHERE checkpoint_ns = '' GROUP BY thread_id ORDER BY newest DESC"
    ).fetchall()
    return [row[0] for row in rows]


def load_messages(agent, thread_id: str) -> list:
    """The saved messages of one conversation, oldest first."""
    state = agent.get_state({"configurable": {"thread_id": thread_id}})
    return list(state.values.get("messages", []))


def list_conversations(agent, checkpointer, store: BaseStore | None = None,
                       user_id: str | None = None) -> list[Conversation]:
    """Saved conversations that have at least one user message, newest first.

    With a user id, only the conversations of that account are listed.
    Without one (the app runs without accounts) all of them are.
    """
    ids = thread_ids(checkpointer)
    if user_id is not None:
        ids = [thread_id for thread_id in ids if owner_of(store, thread_id) == user_id]
    conversations = []
    for thread_id in ids[:MAX_CONVERSATIONS]:
        title = title_from(load_messages(agent, thread_id))
        if title:
            conversations.append(Conversation(thread_id, title))
    return conversations


# --- whose conversation is whose (accounts on) ------------------------------------------------
#
# A conversation is saved under its id alone, and the id is in the page
# address. Without a record of the owner, anyone who had the address of a
# conversation could read it. The owner is recorded in the long-term store
# when the first question is asked.

OWNERS = ("conversation_owners",)
# Set once the first account has taken over what was there before accounts.
ADOPTED = ("accounts_setup",)


def owner_of(store: BaseStore, thread_id: str) -> str | None:
    """The user id of the account a conversation belongs to, or None."""
    item = store.get(OWNERS, thread_id)
    return item.value["owner"] if item else None


def claim_conversation(store: BaseStore, thread_id: str, user_id: str) -> None:
    """Record that a conversation belongs to this account. A conversation
    that already has an owner keeps it."""
    if owner_of(store, thread_id) is None:
        store.put(OWNERS, thread_id, {"owner": user_id})


def may_open(agent, store: BaseStore, thread_id: str, user_id: str) -> bool:
    """True if this account may see the conversation: it is their own, or
    it is still empty. A conversation that has messages and no owner is
    closed to everyone."""
    owner = owner_of(store, thread_id)
    if owner is not None:
        return owner == user_id
    return not load_messages(agent, thread_id)


def adopt_existing(store: BaseStore, checkpointer, user_id: str) -> bool:
    """Give what was saved before there were accounts to this account: the
    conversations nobody owns and the remembered profile. Returns True if
    it was done.

    This happens once, for the first account that opens the app. A later
    call does nothing, whoever makes it.
    """
    if store.get(ADOPTED, "done"):
        return False
    store.put(ADOPTED, "done", {"by": user_id})
    for thread_id in thread_ids(checkpointer):
        claim_conversation(store, thread_id, user_id)
    for key, value in load_profile(store, DEFAULT_USER).items():
        save_preference(store, user_id, key, value)
    forget_profile(store, DEFAULT_USER)
    return True
