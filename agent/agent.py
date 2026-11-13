"""Builds the agent: a model, a list of tools and a system prompt.

create_agent wires these into a ReAct loop:
model decides -> tool runs -> model reads the result -> repeat or answer.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRequest,
    before_agent,
    dynamic_prompt,
    wrap_tool_call,
)

from langchain_core.messages import ToolMessage

from agent.config import (
    FALLBACK_MODELS,
    MAX_TOOL_ROUNDS,
    MODEL_NAME,
    check_keys,
)
from agent.countries import find_country, is_mentioned
from agent.memory import (
    DEFAULT_USER,
    UserContext,
    load_profile,
    make_fact_extractor,
    profile_for_prompt,
    remember_from_message,
)
from agent.memory_tools import MEMORY_TOOLS
from agent.models import make_model
from agent.prompts import build_system_prompt
from agent.report.tool import create_market_report
from agent.tools import TOOLS

# The chat agent's tools: the report workflow, the single-question tools
# and the memory tools.
ALL_TOOLS = [create_market_report] + TOOLS + MEMORY_TOOLS


@dynamic_prompt
def prompt_with_profile(request: ModelRequest) -> str:
    """Middleware that builds the system prompt before every model call.

    It adds what is saved about the user, read fresh from the store each
    time, so a preference saved a moment ago is already visible.
    """
    prompt = build_system_prompt()
    store = request.runtime.store
    if store is None:
        return prompt
    user_id = getattr(request.runtime.context, "user_id", None) or DEFAULT_USER
    return prompt + profile_for_prompt(load_profile(store, user_id))


# Tools whose "country" argument must come from the user, not from the model.
COUNTRY_TOOLS = {"create_market_report", "get_demand_trend"}


def country_came_from_user(country_name: str, messages: list, saved_region: str) -> bool:
    """True if the country in a tool call was named by the user, in this
    conversation or in their saved profile."""
    country = find_country(country_name)
    if country is None:
        return True   # not a recognised country; the tool reports that itself
    said = " ".join(m.content for m in messages
                    if getattr(m, "type", "") == "human" and isinstance(m.content, str))
    return is_mentioned(country, f"{said} {saved_region}")


@wrap_tool_call
def require_country_from_user(request, handler):
    """Middleware around every tool call: stop a market tool from running
    for a country the user never mentioned.

    The prompt tells the model to ask when no country is given, but in
    testing it filled in "United States" by itself. This check is code, so
    it cannot be skipped.
    """
    call = request.tool_call
    if call["name"] in COUNTRY_TOOLS:
        store, context = request.runtime.store, request.runtime.context
        user_id = getattr(context, "user_id", None) or DEFAULT_USER
        saved_region = load_profile(store, user_id).get("region", "") if store else ""
        country = str(call["args"].get("country", ""))
        if not country_came_from_user(country, request.state["messages"], saved_region):
            return ToolMessage(
                content="Which country should I look at? You have not named one "
                        "yet, and I do not want to guess.",
                tool_call_id=call["id"], name=call["name"])
    return handler(request)


def make_profile_capture(extract):
    """Build the middleware that saves lasting facts from each new user
    message before the agent starts answering.

    A before_agent hook runs once per user message, ahead of the first
    model call, so the profile in the system prompt is already up to date.
    """
    @before_agent
    def capture_profile(state, runtime) -> None:
        if runtime.store is None or not state["messages"]:
            return None
        last = state["messages"][-1]
        if getattr(last, "type", "") != "human" or not isinstance(last.content, str):
            return None
        user_id = getattr(runtime.context, "user_id", None) or DEFAULT_USER
        remember_from_message(runtime.store, user_id, last.content, extract)
        return None

    return capture_profile


def assemble_agent(model, fallback_models: list, tools: list,
                   checkpointer=None, store=None, extract_facts=None):
    """Wire a model, its backups, the tools and the memory into an agent.

    Middleware wraps every model call:
    - capture_profile saves lasting facts from the user's new message;
    - prompt_with_profile writes the system prompt, including the user's
      saved profile;
    - require_country_from_user blocks a market tool call for a country the
      user never named;
    - ModelFallbackMiddleware repeats a failed call with a backup model.
    """
    middleware = []
    if extract_facts is not None:
        middleware.append(make_profile_capture(extract_facts))
    middleware.append(prompt_with_profile)
    middleware.append(require_country_from_user)
    if fallback_models:
        middleware.append(ModelFallbackMiddleware(*fallback_models))

    return create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        checkpointer=checkpointer,   # short-term memory: the conversation
        store=store,                 # long-term memory: the user profile
        context_schema=UserContext,
    )


def build_agent(model_name: str = MODEL_NAME,
                fallback_names: list[str] | None = None,
                checkpointer=None, store=None):
    """Create the market research agent with its real models and tools.

    Without a checkpointer the agent has no memory between calls; pass the
    pair from agent.memory.open_memory() to give it one.
    """
    check_keys()
    if fallback_names is None:
        fallback_names = FALLBACK_MODELS

    return assemble_agent(
        model=make_model(model_name),
        fallback_models=[make_model(name) for name in fallback_names],
        tools=ALL_TOOLS,
        checkpointer=checkpointer,
        store=store,
        # Facts are only captured when there is a store to save them in.
        extract_facts=make_fact_extractor(make_model(model_name)) if store else None,
    )


def stream_steps(agent, message: str, thread_id: str, user_id: str = DEFAULT_USER):
    """Send one new message to a conversation and yield each new message as
    it happens: the model's tool requests, the tool results, the answer.

    Only the new message is sent. The checkpointer loads the rest of the
    conversation from the thread id.

    Args:
        agent: The agent returned by build_agent().
        message: What the user just typed.
        thread_id: Identifies the conversation.
        user_id: Identifies whose saved profile to use.
    """
    config = {
        "configurable": {"thread_id": thread_id},
        # Each tool round is two graph steps (model, then tools), plus one
        # final model step for the answer.
        "recursion_limit": MAX_TOOL_ROUNDS * 2 + 1,
    }

    for update in agent.stream(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
        context=UserContext(user_id=user_id),
        stream_mode="updates",
    ):
        for node_output in update.values():
            if not node_output:
                continue
            for item in node_output.get("messages", []):
                yield item
