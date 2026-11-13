"""Builds the agent: a model, a list of tools and a system prompt.

create_agent wires these into a ReAct loop:
model decides -> tool runs -> model reads the result -> repeat or answer.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_openai import ChatOpenAI

from agent.config import (
    FALLBACK_MODELS,
    MAX_TOOL_ROUNDS,
    MODEL_NAME,
    MODEL_TIMEOUT_SECONDS,
    OPENROUTER_BASE_URL,
    TEMPERATURE,
    check_keys,
    get_key,
)
from agent.prompts import build_system_prompt
from agent.tools import TOOLS


def make_model(name: str) -> ChatOpenAI:
    """Create a chat model that is reached through OpenRouter.

    OpenRouter speaks the same API as OpenAI, so the OpenAI client works
    once it is pointed at OpenRouter's address.
    """
    return ChatOpenAI(
        model=name,
        base_url=OPENROUTER_BASE_URL,
        api_key=get_key("OPENROUTER_API_KEY"),
        temperature=TEMPERATURE,
        timeout=MODEL_TIMEOUT_SECONDS,
    )


def assemble_agent(model, fallback_models: list, tools: list):
    """Wire a model, its backups and the tools into an agent.

    Middleware wraps every model call. If the call fails, for example
    because the model is down or rate limited, ModelFallbackMiddleware
    repeats the same call with the next backup model.
    """
    middleware = []
    if fallback_models:
        middleware.append(ModelFallbackMiddleware(*fallback_models))

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=build_system_prompt(),
        middleware=middleware,
    )


def build_agent(model_name: str = MODEL_NAME,
                fallback_names: list[str] | None = None):
    """Create the market research agent with its real models and tools."""
    check_keys()
    if fallback_names is None:
        fallback_names = FALLBACK_MODELS

    return assemble_agent(
        model=make_model(model_name),
        fallback_models=[make_model(name) for name in fallback_names],
        tools=TOOLS,
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
