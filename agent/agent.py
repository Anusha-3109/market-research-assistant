"""Builds the agent: a model, a list of tools and a system prompt.

create_agent wires these into a ReAct loop:
model decides -> tool runs -> model reads the result -> repeat or answer.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelFallbackMiddleware,
    ModelRequest,
    ModelResponse,
    before_agent,
    dynamic_prompt,
    wrap_model_call,
    wrap_tool_call,
)

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from agent.answer_length import (
    answer_limit,
    is_an_answer,
    was_cut_off,
    with_cut_off_note,
)
from agent import usage
from agent.approval import SAVE_APPROVAL_CONFIG, Pause, Progress, read_pause
from agent.config import (
    FALLBACK_MODELS,
    MAX_TOOL_ROUNDS,
    MODEL_NAME,
    TEMPERATURE,
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
from agent.source_check import check_answer
from agent.language import answer_instruction
from agent.styles import style_for_prompt
from agent.tracing import trace_labels
from agent.app_settings import custom_prompt
from agent.tools import TOOLS

# The chat agent's tools: the report workflow, the single-question tools
# and the memory tools.
ALL_TOOLS = [create_market_report] + TOOLS + MEMORY_TOOLS


def enabled_tools(disabled=()) -> list:
    """The tools the agent may use: all of them except those switched off on
    the Admin page. forget_preferences follows remember_preference."""
    off = set(disabled)
    if "remember_preference" in off:
        off.add("forget_preferences")
    return [tool for tool in ALL_TOOLS if tool.name not in off]


@dynamic_prompt
def prompt_with_profile(request: ModelRequest) -> str:
    """Middleware that builds the system prompt before every model call.

    It adds what is saved about the user, read fresh from the store each
    time, so a preference saved a moment ago is already visible.
    """
    # The prompt set on the Admin page, or the built-in one.
    prompt = custom_prompt(request.runtime.store) or build_system_prompt()
    # The answer style comes last, so the model reads it after the saved
    # profile and knows it overrides a remembered style.
    how_to_write = style_for_prompt(getattr(request.runtime.context, "answer_style", None))
    # The language comes after everything else: it applies to the whole answer.
    how_to_write += answer_instruction(getattr(request.runtime.context, "language", None))
    store = request.runtime.store
    if store is None:
        return prompt + how_to_write
    user_id = getattr(request.runtime.context, "user_id", None) or DEFAULT_USER
    return prompt + profile_for_prompt(load_profile(store, user_id)) + how_to_write


@wrap_model_call
def keep_sources(request: ModelRequest, handler):
    """Middleware that checks each answer the model writes: if the tools
    reported where their information came from and the answer links to
    nothing, the links are added (agent/source_check.py).

    It wraps the model call and corrects the answer before it is saved, so
    the conversation only ever holds the checked version.
    """
    response = handler(request)
    checked = [check_answer(message, request.messages) if isinstance(message, AIMessage)
               else message for message in response.result]
    return ModelResponse(result=checked, structured_response=response.structured_response)


@wrap_model_call
def limit_answer_length(request: ModelRequest, handler):
    """Middleware that applies the user's "Maximum answer length" to each
    model call of the chat agent (agent/answer_length.py).

    When the limit cuts the model off, what happens depends on what it was
    writing:
    - an answer keeps what was written and gets a note saying it was cut;
    - a step, such as a request for a tool, is useless half-written, so the
      model is asked for it again without the limit.
    """
    limit = answer_limit(request.runtime.context)
    if limit is None:
        return handler(request)
    limited = request.override(model_settings={**request.model_settings, "max_tokens": limit})
    response = handler(limited)

    replies = [message for message in response.result if isinstance(message, AIMessage)]
    if any(was_cut_off(message) and not is_an_answer(message) for message in replies):
        return handler(request)

    noted = [with_cut_off_note(message)
             if isinstance(message, AIMessage) and was_cut_off(message) else message
             for message in response.result]
    return ModelResponse(result=noted, structured_response=response.structured_response)


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

    Reading the message is a model call of its own. What it used is kept
    with the user's message, so the app can count it with that question.
    The message is replaced by a copy that carries the figures; its words
    are untouched and the figures are never sent to a model.
    """
    @before_agent
    def capture_profile(state, runtime) -> dict | None:
        if runtime.store is None or not state["messages"]:
            return None
        last = state["messages"][-1]
        if getattr(last, "type", "") != "human" or not isinstance(last.content, str):
            return None
        user_id = getattr(runtime.context, "user_id", None) or DEFAULT_USER
        with usage.collecting() as calls:
            remember_from_message(runtime.store, user_id, last.content, extract)
        if not calls:
            return None
        used = usage.to_record(usage.total(calls))
        noted = last.model_copy(update={"response_metadata": {
            **last.response_metadata, usage.BACKGROUND_KEY: used}})
        # Same id, so this replaces the message instead of adding one.
        return {"messages": [noted]}

    return capture_profile


def assemble_agent(model, fallback_models: list, tools: list,
                   checkpointer=None, store=None, extract_facts=None):
    """Wire a model, its backups, the tools and the memory into an agent.

    Middleware wraps every model call:
    - capture_profile saves lasting facts from the user's new message;
    - prompt_with_profile writes the system prompt, including the user's
      saved profile;
    - keep_sources puts back the link to a source if the answer left it out;
    - limit_answer_length applies the user's cap on the length of an answer;
    - require_country_from_user blocks a market tool call for a country the
      user never named;
    - ModelFallbackMiddleware repeats a failed call with a backup model.
    - HumanInTheLoopMiddleware pauses for the user's approval before a
      report is saved to a file.
    """
    middleware = []
    if extract_facts is not None:
        middleware.append(make_profile_capture(extract_facts))
    middleware.append(prompt_with_profile)
    middleware.append(keep_sources)
    middleware.append(limit_answer_length)
    middleware.append(require_country_from_user)
    if fallback_models:
        middleware.append(ModelFallbackMiddleware(*fallback_models))
    if checkpointer is not None:
        # A pause needs a saved conversation to come back to, so approval
        # is only switched on when the agent has a checkpointer.
        middleware.append(HumanInTheLoopMiddleware(interrupt_on=SAVE_APPROVAL_CONFIG))

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
                checkpointer=None, store=None,
                temperature: float = TEMPERATURE, disabled_tools=()):
    """Create the market research agent with its real models and tools.

    Without a checkpointer the agent has no memory between calls; pass the
    pair from agent.memory.open_memory() to give it one.
    """
    check_keys()
    if fallback_names is None:
        fallback_names = FALLBACK_MODELS

    return assemble_agent(
        model=make_model(model_name, temperature),
        fallback_models=[make_model(name) for name in fallback_names],
        tools=enabled_tools(disabled_tools),
        checkpointer=checkpointer,
        store=store,
        # Facts are only captured when there is a store to save them in.
        extract_facts=make_fact_extractor(make_model(model_name)) if store else None,
    )


def _run(agent, payload, thread_id: str, context: UserContext):
    """Run the agent and yield what happens: each new message, a Progress
    line while a long tool is working, and a Pause if the agent stops to
    wait for the user."""
    config = {
        # How the run is named and labelled in a trace (agent/tracing.py).
        **trace_labels("Markavi chat", "chat", thread_id, context),
        "configurable": {"thread_id": thread_id},
        # Each tool round is two graph steps (model, then tools), plus one
        # final model step for the answer.
        "recursion_limit": MAX_TOOL_ROUNDS * 2 + 1,
    }

    # Two streams at once: "updates" carries each new message, "custom"
    # carries the progress lines a tool sends while it is still running.
    for mode, chunk in agent.stream(payload, config=config,
                                    context=context,
                                    stream_mode=["updates", "custom"]):
        if mode == "custom":
            if isinstance(chunk, dict) and "progress" in chunk:
                yield Progress(str(chunk["progress"]))
            continue

        for node, output in chunk.items():
            if node == "__interrupt__":
                # The agent has stopped and saved its state.
                for interrupt in output:
                    pause = read_pause(interrupt.value)
                    if pause:
                        yield pause
                continue
            for item in (output or {}).get("messages", []):
                yield item


def stream_steps(agent, message: str, thread_id: str, user_id: str = DEFAULT_USER,
                 context: UserContext | None = None):
    """Send one new message to a conversation and yield each new message as
    it happens: the model's tool requests, the tool results, the answer.
    If the agent stops for the user's approval, a Pause is yielded last.

    Only the new message is sent. The checkpointer loads the rest of the
    conversation from the thread id.

    Args:
        agent: The agent returned by build_agent().
        message: What the user just typed.
        thread_id: Identifies the conversation.
        user_id: Identifies whose saved profile to use.
        context: The user and their settings together; replaces user_id
            when given.
    """
    payload = {"messages": [{"role": "user", "content": message}]}
    yield from _run(agent, payload, thread_id, context or UserContext(user_id=user_id))


def resume_steps(agent, answer: dict, thread_id: str, user_id: str = DEFAULT_USER,
                 context: UserContext | None = None):
    """Continue a paused conversation with the user's answer.

    Command(resume=...) tells LangGraph to carry on from the saved state
    and hand the answer to the step that was waiting.

    Args:
        answer: Built with review_answer() or save_answer() in approval.py.
    """
    yield from _run(agent, Command(resume=answer), thread_id,
                    context or UserContext(user_id=user_id))


def pending_pause(agent, thread_id: str) -> Pause | None:
    """Return the Pause a conversation is waiting on, if any. Used when a
    conversation is opened again after the program was closed."""
    state = agent.get_state({"configurable": {"thread_id": thread_id}})
    for interrupt in state.interrupts:
        pause = read_pause(interrupt.value)
        if pause:
            return pause
    return None


def settle_stopped_turn(agent, thread_id: str) -> bool:
    """Tidy a conversation whose last turn was cut off (the user pressed
    Stop, or closed the page, while a tool was running).

    The saved conversation then ends with the model's request for a tool
    and no result. The model refuses to continue from that, so each open
    request is given the result "stopped". Returns True if anything was
    tidied. Not to be called while the agent is waiting for an approval:
    that state is complete and must stay as it is.
    """
    config = {"configurable": {"thread_id": thread_id}}
    messages = agent.get_state(config).values.get("messages", [])
    if not messages or not isinstance(messages[-1], AIMessage) or not messages[-1].tool_calls:
        return False
    stopped = [ToolMessage("Stopped by the user before this finished.",
                           tool_call_id=call["id"], name=call["name"])
               for call in messages[-1].tool_calls]
    agent.update_state(config, {"messages": stopped}, as_node="tools")
    return True
