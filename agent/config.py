"""Settings for the agent, kept in one place.

Keys are read from the .env file. Everything else is a plain constant so it
is easy to find and change.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Model: any OpenRouter model id that supports tool calling.
MODEL_NAME = "openai/gpt-4.1-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Low temperature: research answers should be factual and repeatable.
TEMPERATURE = 0.2

# How many results each web search returns.
SEARCH_MAX_RESULTS = 5

# Upper limit on tool rounds for one question. One round is "the model asks
# for tools, the tools run". It stops a runaway loop from burning credit.
MAX_TOOL_ROUNDS = 12

REQUIRED_KEYS = ["OPENROUTER_API_KEY", "TAVILY_API_KEY"]


class MissingKeyError(RuntimeError):
    """Raised when a required API key is not set."""


def get_key(name: str) -> str:
    """Return an API key from the environment, or raise a clear error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise MissingKeyError(
            f"{name} is not set. Add it to the .env file in the project folder "
            "(see .env.example for the expected names)."
        )
    return value


def check_keys() -> None:
    """Fail early, with a readable message, if any required key is missing."""
    for name in REQUIRED_KEYS:
        get_key(name)
