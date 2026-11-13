"""Creates the chat model. Kept in its own file so both the chat agent and
the report workflow can use it without importing each other."""

from langchain_openai import ChatOpenAI

from agent.config import (
    MODEL_TIMEOUT_SECONDS,
    OPENROUTER_BASE_URL,
    TEMPERATURE,
    get_key,
)


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
