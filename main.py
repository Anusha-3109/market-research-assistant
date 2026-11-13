"""Terminal chat for testing the agent.

Run with:  python main.py
It prints every step of the ReAct loop so you can see what the agent does.
The Streamlit app replaces this later.
"""

import sys

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.agent import build_agent, stream_steps
from agent.config import MODEL_NAME, REPORT_HEADING, MissingKeyError
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
    elif isinstance(message, ToolMessage):
        first_line = str(message.content).splitlines()[0] if message.content else ""
        print(f"  [tool result] {len(str(message.content))} characters: {first_line[:80]}")
    elif isinstance(message, AIMessage):
        print(f"\nAssistant:\n{message.content}\n")
        # A full report is checked against the format rules.
        if isinstance(message.content, str) and REPORT_HEADING in message.content:
            print(format_check(check_report(message.content)) + "\n")


def run_turn(agent, history: list, question: str) -> None:
    """Send one question to the agent and add the new messages to history."""
    history.append(HumanMessage(question))
    try:
        for message in stream_steps(agent, history):
            print_step(message)
            history.append(message)
    except GraphRecursionError:
        print("\nThe agent reached its step limit before finishing. "
              "Try a narrower question.\n")
    except Exception as error:  # model or network failure
        print(f"\nSomething went wrong while answering: {error}\n")


def main() -> None:
    # Windows terminals may not default to UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        agent = build_agent()
    except MissingKeyError as error:
        print(f"Setup problem: {error}")
        return

    history: list = []

    # Questions passed on the command line are asked in order (for testing).
    for question in sys.argv[1:]:
        print(f"You: {question}")
        run_turn(agent, history, question)
    if sys.argv[1:]:
        return

    print("Market research assistant. Type 'quit' to stop.\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if question:
            run_turn(agent, history, question)


if __name__ == "__main__":
    main()
