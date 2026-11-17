"""The source check: an answer never loses the link to where its facts
came from.

The model is told to end every fact with its source, and almost always
does. Now and then it does not: in test runs the Friendly answer style kept
the figures but left the link out in about one answer in thirty. An
instruction can be forgotten, so this is checked by code as well, the same
way the report workflow checks what the model writes.

The check looks at the tools the model used for this question. If they
reported where their information came from and the finished answer links
to nothing at all, the addresses are added at the end.

Which addresses are trusted
---------------------------
A tool's result is partly written by this app (the "URL:" and "Source:"
lines) and partly copied from the web (search extracts, the text of a
page). Only the app's own lines are read. Otherwise a web page could carry
a line such as "Source: https://..." in its text and have that link added
to an answer. So each tool has its own reader, which knows where in that
tool's result the app's lines are; a tool without a reader adds nothing.
"""

import re

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# The most links added to one answer. A search can find many pages; a long
# row of links under a short answer helps nobody.
MAX_SOURCES_ADDED = 5

# A search lists each page as "[1] Title" with "URL: <address>" on the very
# next line. An address anywhere else in the result is web text.
LISTED_PAGE = re.compile(r"^\[\d+\] [^\n]*\nURL:\s*(https?://\S+)", re.MULTILINE)
URL_LINE = re.compile(r"^URL:\s*(https?://\S+)", re.MULTILINE)
SOURCE_LINE = re.compile(r"^Source:\s*(https?://\S+)", re.MULTILINE)


def pages_listed(result: str) -> list[str]:
    """The pages a search found."""
    return LISTED_PAGE.findall(result)


def page_opened(result: str) -> list[str]:
    """The one page that was read. Its address is in the heading, before
    the first empty line; everything after that is the page's own text."""
    heading = result.split("\n\n", 1)[0]
    return URL_LINE.findall(heading)[:1]


def source_lines(result: str) -> list[str]:
    """The "Source:" lines of a result that this app builds line by line
    from a data service, with no free text from the web in it."""
    return SOURCE_LINE.findall(result)


# How to read each tool's result. A new research tool is added here.
READERS = {
    "web_search": pages_listed,
    "search_news": pages_listed,
    "read_webpage": page_opened,
    "get_company_financials": source_lines,
    "get_demand_trend": source_lines,
}


def tool_results_this_turn(messages: list) -> list[ToolMessage]:
    """Every tool result since the user's latest message."""
    results: list[ToolMessage] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            results = []
        elif isinstance(message, ToolMessage) and isinstance(message.content, str):
            results.append(message)
    return results


def sources_found(messages: list) -> list[str]:
    """The addresses the tools reported for this question, in the order
    they were found, each once."""
    found: list[str] = []
    for result in tool_results_this_turn(messages):
        read = READERS.get(result.name or "")
        if read is None:
            continue
        for url in read(result.content):
            if url not in found:
                found.append(url)
    return found


def with_sources(answer: str, messages: list) -> str:
    """The answer, with its sources added if it has none.

    messages: the conversation up to, but not including, this answer.
    """
    if "http://" in answer or "https://" in answer:
        return answer
    found = sources_found(messages)
    if not found:
        return answer
    links = " ".join(f"[source]({url})" for url in found[:MAX_SOURCES_ADDED])
    return f"{answer.rstrip()}\n\nSources: {links}"


def check_answer(message: AIMessage, messages: list) -> AIMessage:
    """Return the model's message with its sources restored if needed.

    A message that asks for a tool is not an answer yet and is left alone.
    """
    if message.tool_calls or not isinstance(message.content, str) or not message.content.strip():
        return message
    checked = with_sources(message.content, messages)
    if checked == message.content:
        return message
    return message.model_copy(update={"content": checked})
