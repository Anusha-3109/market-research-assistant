"""Tools that let the agent write to its long-term memory.

Reading the profile needs no tool: middleware adds it to the system prompt
on every turn (see agent.py). These tools are for saving and deleting.
"""

from langchain.tools import ToolRuntime, tool

from agent.memory import (
    DEFAULT_USER,
    UserContext,
    forget_profile,
    save_preference,
)


def _user_id(runtime: ToolRuntime[UserContext]) -> str:
    return getattr(runtime.context, "user_id", None) or DEFAULT_USER


@tool
def remember_preference(key: str, value: str, runtime: ToolRuntime[UserContext]) -> str:
    """Remember one lasting fact about the user for future conversations.

    Call this when the user states their target country or region, their
    industry, their business idea, or how they like reports written. Do not
    save anything else, and never save personal or sensitive details such as
    names, contact details, health or finances.

    Args:
        key: One of "region", "industry", "business_idea", "report_style".
        value: The fact, in a few words, for example "Germany".
    """
    if runtime.store is None:
        return "Long-term memory is not available in this session."
    return save_preference(runtime.store, _user_id(runtime), key, value)


@tool
def forget_preferences(runtime: ToolRuntime[UserContext]) -> str:
    """Delete everything remembered about the user. Call this when the user
    asks you to forget them or to clear their saved preferences."""
    if runtime.store is None:
        return "Long-term memory is not available in this session."
    return forget_profile(runtime.store, _user_id(runtime))


MEMORY_TOOLS = [remember_preference, forget_preferences]
