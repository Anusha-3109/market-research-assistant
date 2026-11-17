"""What a user interface needs to show conversations.

Nothing here imports Streamlit, so it can be tested without a browser and
reused by any interface.

- turn the saved messages of a conversation into simple blocks to display;
- list the saved conversations with a title each.
"""

import uuid
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.citations import Source, number_citations, titles_in_results, without_references
from agent.config import REPORT_HEADING
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
    rows = checkpointer.conn.execute(
        "SELECT thread_id, MAX(rowid) AS newest FROM checkpoints "
        "WHERE checkpoint_ns = '' GROUP BY thread_id ORDER BY newest DESC"
    ).fetchall()
    return [row[0] for row in rows]


def load_messages(agent, thread_id: str) -> list:
    """The saved messages of one conversation, oldest first."""
    state = agent.get_state({"configurable": {"thread_id": thread_id}})
    return list(state.values.get("messages", []))


def list_conversations(agent, checkpointer) -> list[Conversation]:
    """Saved conversations that have at least one user message, newest first."""
    conversations = []
    for thread_id in thread_ids(checkpointer)[:MAX_CONVERSATIONS]:
        title = title_from(load_messages(agent, thread_id))
        if title:
            conversations.append(Conversation(thread_id, title))
    return conversations
