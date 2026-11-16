"""Showing a conversation, and running one turn of it."""

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.agent import resume_steps, stream_steps
from agent.approval import Pause, Progress
from agent.report_check import format_check
from agent.session import Block, describe_tool_call, report_title
from agent.tools import safe_filename

SAVE_QUESTION = "Save this report."


def render_block(block: Block, index: int, is_latest_report: bool) -> str | None:
    """Show one chat bubble. Returns a question to send if the user pressed
    a button in it (for example "Save to file"), otherwise None."""
    action = None
    with st.chat_message(block.role):
        if block.activity:
            # What the agent did, tucked away so the answer stays in front.
            with st.expander(f"How this was researched ({len(block.activity)} steps)",
                             type="compact"):
                for line in block.activity:
                    st.caption(line)
        if block.text:
            st.markdown(block.text)
        if block.report:
            action = render_report(block, index, is_latest_report)
    return action


def render_report(block: Block, index: int, is_latest: bool) -> str | None:
    """Show a report as a document, with its check result and buttons."""
    action = None
    title = report_title(block.report)

    with st.container(key=f"report_panel_{index}"):
        if block.problems is not None:
            if block.problems:
                st.warning(format_check(block.problems), title="Report check")
            else:
                st.badge("Report check passed", icon=":material/check:", color="green")

        st.markdown(block.report)

        with st.container(horizontal=True):
            # A download goes to the user's own computer, so it needs no
            # approval. Saving on the server does: that goes through the
            # agent, which asks first.
            st.download_button(
                "Download", data=block.report, file_name=safe_filename(title),
                mime="text/markdown", icon=":material/download:",
                key=f"download_{index}")
            if is_latest and st.button("Save to reports folder", icon=":material/save:",
                                       key=f"save_{index}"):
                action = SAVE_QUESTION
    return action


def render_history(blocks: list[Block]) -> str | None:
    """Show the whole conversation. Returns a question to send if a button
    inside it was pressed."""
    report_indexes = [index for index, block in enumerate(blocks) if block.report]
    latest_report = report_indexes[-1] if report_indexes else None

    action = None
    for index, block in enumerate(blocks):
        action = render_block(block, index, index == latest_report) or action
    return action


def play(steps) -> Pause | None:
    """Show the agent working, step by step, inside the current bubble.

    Returns the Pause if the agent stopped to wait for an approval.
    """
    pause = None
    with st.status(":shimmer[Working on it]", type="compact", expanded=True) as status:
        try:
            for item in steps:
                if isinstance(item, Pause):
                    pause = item
                elif isinstance(item, Progress):
                    st.caption(item.text)
                elif isinstance(item, AIMessage):
                    for call in item.tool_calls:
                        st.caption(describe_tool_call(call["name"], call["args"]))
                elif isinstance(item, ToolMessage):
                    first_line = str(item.content).splitlines()[0] if item.content else ""
                    if first_line.startswith("Source used"):
                        st.caption(first_line)
            label = "Waiting for you" if pause else "Done"
            status.update(label=label, state="complete", expanded=False)
        except GraphRecursionError:
            status.update(label="Stopped", state="error")
            st.error("The assistant reached its step limit before finishing. "
                     "Try a narrower question.")
            st.stop()   # keep the message on screen
        except Exception as error:  # model or network failure
            status.update(label="Something went wrong", state="error")
            st.error(f"The assistant could not answer: {error}",
                     title="Something went wrong")
            st.stop()
    return pause


def run_turn(agent, thread_id: str, question: str) -> Pause | None:
    """Send the user's question and show the agent's steps as they happen."""
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        return play(stream_steps(agent, question, thread_id))


def run_resume(agent, thread_id: str, answer: dict) -> Pause | None:
    """Continue a paused conversation with the user's answer."""
    with st.chat_message("assistant"):
        return play(resume_steps(agent, answer, thread_id))
