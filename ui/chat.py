"""Showing a conversation, and running one turn of it."""

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.agent import stream_steps
from agent.approval import Pause
from agent.report_check import format_check
from agent.session import Block, describe_tool_call


def render_block(block: Block, index: int) -> None:
    """Show one chat bubble."""
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
            render_report(block, index)


def render_report(block: Block, index: int) -> None:
    """Show a report as a document, with its check result."""
    with st.container(key=f"report_panel_{index}"):
        if block.problems is not None:
            if block.problems:
                st.warning(format_check(block.problems), title="Report check")
            else:
                st.badge("Report check passed", icon=":material/check:", color="green")
        st.markdown(block.report)


def render_history(blocks: list[Block]) -> None:
    for index, block in enumerate(blocks):
        render_block(block, index)


def run_turn(agent, thread_id: str, question: str) -> Pause | None:
    """Send the user's question, showing the agent's steps as they happen.

    Returns the Pause if the agent stopped to wait for an approval.
    """
    with st.chat_message("user"):
        st.markdown(question)

    pause = None
    with st.chat_message("assistant"):
        with st.status(":shimmer[Working on it]", type="compact", expanded=True) as status:
            try:
                for item in stream_steps(agent, question, thread_id):
                    if isinstance(item, Pause):
                        pause = item
                    elif isinstance(item, AIMessage):
                        for call in item.tool_calls:
                            st.caption(describe_tool_call(call["name"], call["args"]))
                    elif isinstance(item, ToolMessage):
                        first_line = str(item.content).splitlines()[0] if item.content else ""
                        if first_line.startswith("Source used"):
                            st.caption(first_line)
                status.update(label="Done", state="complete", expanded=False)
            except GraphRecursionError:
                status.update(label="Stopped", state="error")
                st.error("The assistant reached its step limit before finishing. "
                         "Try a narrower question.")
            except Exception as error:  # model or network failure
                status.update(label="Something went wrong", state="error")
                st.error(f"The assistant could not answer: {error}",
                         title="Something went wrong")
    return pause
