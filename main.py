"""Terminal chat for testing the agent.

    python main.py                      start a new conversation
    python main.py --thread <id>        continue an earlier conversation
    python main.py "question" ...       ask the questions and exit

It prints every step of the agent loop so you can see what the agent does.
When the agent stops for an approval, you type your answer. In the
"questions and exit" form, the next item on the command line is used as the
answer. The Streamlit app replaces this later.
"""

import sys
import uuid

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.agent import build_agent, pending_pause, resume_steps, stream_steps
from agent.approval import (
    SAVE_KIND,
    Pause,
    Progress,
    parse_review_reply,
    parse_save_reply,
)
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
        # Its progress lines were already printed live, as they happened.
        details = message.artifact or {}
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


def describe_pause(pause: Pause) -> str:
    """The text shown to the user when the agent is waiting for them."""
    if pause.kind == SAVE_KIND:
        return (f"\n[approval needed] Save this report as {pause.data['filename']}?\n"
                f"  Type: approve | reject | title <new title>")

    data = pause.data
    lines = [f"\n[approval needed] Competitors found for {data['product']} "
             f"in {data['country']}:"]
    for number, competitor in enumerate(data["competitors"], start=1):
        lines.append(f"  {number}. {competitor['name']}  "
                     f"({competitor['website'] or 'no website found'})")
    if data["left_out"]:
        lines.append(f"  Verified but left out: {', '.join(data['left_out'])}")
    for dropped in data["dropped"]:
        lines.append(f"  Dropped: {dropped['name']} ({dropped['reason'][:70]})")
    lines.append("  Type: approve | remove 2,4 | add <company> | "
                 "remove 4; add <company> | cancel")
    return "\n".join(lines)


def answer_for(pause: Pause, reply: str) -> dict:
    """Turn the typed reply into the answer that resumes the agent."""
    if pause.kind == SAVE_KIND:
        return parse_save_reply(reply)
    names = [competitor["name"] for competitor in pause.data["competitors"]]
    return parse_review_reply(reply, names)


def play(steps, ask_user) -> Pause | None:
    """Print each step. Return the Pause if the agent stopped for the user."""
    pause = None
    for item in steps:
        if isinstance(item, Pause):
            pause = item
        elif isinstance(item, Progress):
            print(f"  [workflow] {item.text}")
        else:
            print_step(item)
    return pause


def run_turn(agent, thread_id: str, question: str, ask_user) -> None:
    """Send one question to the conversation and print what happens. While
    the agent keeps stopping for approval, ask the user and continue.

    No history is kept here: the checkpointer stores the conversation under
    the thread id and loads it again for the next question.

    Args:
        ask_user: A function that shows a prompt and returns the reply.
    """
    try:
        pause = play(stream_steps(agent, question, thread_id), ask_user)
        while pause is not None:
            reply = ask_user(describe_pause(pause))
            pause = play(resume_steps(agent, answer_for(pause, reply), thread_id), ask_user)
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

    scripted = bool(questions)
    queue = list(questions)

    def ask_user(prompt: str) -> str:
        """Show an approval prompt and get the reply: typed by the user, or
        taken from the command line when the run is scripted."""
        print(prompt)
        if not scripted:
            return input("Your decision: ").strip()
        if not queue:
            print("  (no answer given on the command line; leaving it waiting)")
            raise SystemExit(0)
        reply = queue.pop(0)
        print(f"Your decision: {reply}")
        return reply

    # A conversation that was closed while waiting for an approval.
    waiting = pending_pause(agent, thread_id)
    if waiting is not None:
        print("This conversation is waiting for your decision.")
        reply = ask_user(describe_pause(waiting))
        pause = play(resume_steps(agent, answer_for(waiting, reply), thread_id), ask_user)
        while pause is not None:
            reply = ask_user(describe_pause(pause))
            pause = play(resume_steps(agent, answer_for(pause, reply), thread_id), ask_user)

    if scripted:
        # Questions passed on the command line are asked in order (for testing).
        while queue:
            question = queue.pop(0)
            print(f"You: {question}")
            run_turn(agent, thread_id, question, ask_user)
        return

    print("Market research assistant. Type 'quit' to stop.\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if question:
            run_turn(agent, thread_id, question, ask_user)


if __name__ == "__main__":
    main()
