"""Builds the agent: a model, a list of tools and a system prompt.

create_agent wires these into a ReAct loop:
model decides -> tool runs -> model reads the result -> repeat or answer.
"""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from agent.config import (
    MAX_TOOL_ROUNDS,
    MODEL_NAME,
    OPENROUTER_BASE_URL,
    TEMPERATURE,
    check_keys,
    get_key,
)
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOLS


def build_agent():
    """Create the market research agent."""
    check_keys()

    # OpenRouter speaks the same API as OpenAI, so the OpenAI client works
    # once it is pointed at OpenRouter's address.
    model = ChatOpenAI(
        model=MODEL_NAME,
        base_url=OPENROUTER_BASE_URL,
        api_key=get_key("OPENROUTER_API_KEY"),
        temperature=TEMPERATURE,
    )

    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )


def stream_steps(agent, messages: list):
    """Run the agent on a conversation and yield each new message as it
    happens: the model's tool requests, the tool results, the final answer.

    Args:
        agent: The agent returned by build_agent().
        messages: The conversation so far, oldest first.
    """
    # Each tool round is two graph steps (model, then tools), plus one final
    # model step for the answer.
    config = {"recursion_limit": MAX_TOOL_ROUNDS * 2 + 1}

    for update in agent.stream(
        {"messages": messages}, config=config, stream_mode="updates"
    ):
        for node_output in update.values():
            if not node_output:
                continue
            for message in node_output.get("messages", []):
                yield message
