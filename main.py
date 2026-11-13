"""Terminal chat for testing the agent.

    python main.py                      start a new conversation
    python main.py --thread <id>        continue an earlier conversation
    python main.py "question" ...       ask the questions and exit

It prints every step of the agent loop so you can see what the agent does.
The Streamlit app replaces this later.
"""

import sys
import uuid

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.agent import build_agent, stream_steps
from agent.config import MODEL_NAME, REPORT_HEADING, MissingKeyError
from agent.memory import open_memory
from agent.report.tool import REPORT_TOOL_NAME
from agent.report_check import check_report, format_check


def print_step(message) -> None:
    """Print one message from the agent loop in a readable form."""
    if isinstance(message, AIMessage):
        # Say so when a backup model answered instead of the main one.
        answered_by = message.response_metadata.get("model_name", "")
        if answered_by and not answered_by.startswith(MODEL_NAME):
            print(f"  [backup model] {answered_by}")

    if isinstance(message, AIMessage) and message.tool_calls:
        for call in message.tool_calls:
            print(f"  [tool call] {call['name']}({call['args']})")
    elif isinstance(message, ToolMessage) and message.name == REPORT_TOOL_NAME:
        # The report workflow's result is the answer itself.
        details = message.artifact or {}
        for line in details.get("log", []):
            print(f"  [workflow] {line}")
        print(f"\nAssistant:\n{message.content}\n")
        if "problems" in details:
            print(format_check(details["problems"]) + "\n")
    elif isinstance(message, ToolMessage):
        first_line = str(message.content).splitlines()[0] if message.content else ""
        print(f"  [tool result] {len(str(message.content))} characters: {first_line[:80]}")
    elif isinstance(message, AIMessage):
        print(f"\nAssistant:\n{message.content}\n")
        # A full report is checked against the format rules.
        if isinstance(message.content, str) and REPORT_HEADING in message.content:
            print(format_check(check_report(message.content)) + "\n")


def run_turn(agent, thread_id: str, question: str) -> None:
    """Send one question to the conversation and print what happens.

    No history is kept here: the checkpointer stores the conversation under
    the thread id and loads it again for the next question.
    """
    try:
        for message in stream_steps(agent, question, thread_id):
            print_step(message)
    except GraphRecursionError:
        print("\nThe agent reached its step limit before finishing. "
              "Try a narrower question.\n")
    except Exception as error:  # model or network failure
        print(f"\nSomething went wrong while answering: {error}\n")


def read_arguments(arguments: list[str]) -> tuple[str, list[str]]:
    """Split the command line into the thread id and the questions.

    Returns a new random thread id when --thread is not given.
    """
    if "--thread" in arguments:
        position = arguments.index("--thread")
        if position + 1 < len(arguments):
            thread_id = arguments[position + 1]
            return thread_id, arguments[:position] + arguments[position + 2:]
        arguments = arguments[:position]
    return uuid.uuid4().hex[:8], arguments


def main() -> None:
    # Windows terminals may not default to UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    thread_id, questions = read_arguments(sys.argv[1:])
    try:
        checkpointer, store = open_memory()
        agent = build_agent(checkpointer=checkpointer, store=store)
    except MissingKeyError as error:
        print(f"Setup problem: {error}")
        return

    print(f"Conversation id: {thread_id}  "
          f"(continue later with: python main.py --thread {thread_id})\n")

    # Questions passed on the command line are asked in order (for testing).
    for question in questions:
        print(f"You: {question}")
        run_turn(agent, thread_id, question)
    if questions:
        return

    print("Market research assistant. Type 'quit' to stop.\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if question:
            run_turn(agent, thread_id, question)


if __name__ == "__main__":
    main()
