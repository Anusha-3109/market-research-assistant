"""Settings for the agent, kept in one place.

Keys are read from the .env file. Everything else is a plain constant so it
is easy to find and change.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# The name shown in the app. Change it here and it changes everywhere.
APP_NAME = "Markavi"
APP_TAGLINE = "Market research before you launch"

# Model: any OpenRouter model id that supports tool calling.
MODEL_NAME = "openai/gpt-4.1-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Backup models, tried in order when the main model fails. Empty means the
# agent uses the main model only. To turn the fallback on, list models from
# other companies here, for example:
#   ["anthropic/claude-haiku-5.5", "google/gemini-3.1-flash-lite"]
FALLBACK_MODELS: list[str] = []

# Give up on one model call after this many seconds and try the next model.
MODEL_TIMEOUT_SECONDS = 90

# Models offered in the app's settings. Each supports tool calling and comes
# from a different company. The key is the OpenRouter id; the value is the
# name shown to the user.
MODEL_CHOICES = {
    "openai/gpt-4.1-mini": "GPT-4.1 mini (OpenAI)",
    "anthropic/claude-haiku-5.5": "Claude Haiku 5.5 (Anthropic)",
    "google/gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite (Google)",
}

# The longest question the app accepts, in characters.
MAX_QUESTION_CHARS = 2000

# Low temperature: research answers should be factual and repeatable.
TEMPERATURE = 0.2

# How many results each web search returns.
SEARCH_MAX_RESULTS = 5

# Longest extract kept from each search result.
SNIPPET_MAX_CHARS = 1200

# Reading a web page: the most we download, and the most text we pass on
# to the model (about 2,500 words).
PAGE_MAX_BYTES = 2_000_000
PAGE_MAX_CHARS = 12_000

# How long to wait for one data source before trying the next one.
SOURCE_TIMEOUT_SECONDS = 15

# How far back the news search looks: "day", "week", "month" or "year".
NEWS_TIME_RANGE = "month"
# The same window in days, for sources that take a number.
NEWS_DAYS = 30

PROJECT_DIR = Path(__file__).resolve().parent.parent


def storage_paths(data_dir: str) -> tuple[Path, Path]:
    """Where saved reports and the memory file go.

    On your own computer DATA_DIR is not set and both stay inside the
    project folder. A deployed copy sets DATA_DIR to a folder that survives
    restarts (a mounted storage bucket), and both go there.

    Returns (reports folder, memory file).
    """
    data_dir = data_dir.strip()
    if not data_dir:
        return PROJECT_DIR / "reports", PROJECT_DIR / "data" / "memory.db"
    root = Path(data_dir)
    return root / "reports", root / "memory.db"


# REPORTS_DIR: folder where saved reports are written.
# MEMORY_DB: the file that holds the agent's memory (conversations and
# user profiles).
REPORTS_DIR, MEMORY_DB = storage_paths(os.getenv("DATA_DIR", ""))

# A deployed copy is opened with this password, so that strangers with the
# link cannot spend the API credit. Not set (as on your own computer): the
# app opens directly.
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()

# The only facts the agent may remember about a user between conversations.
PROFILE_KEYS = ["region", "industry", "business_idea", "report_style"]
PROFILE_VALUE_MAX_CHARS = 200

# Every report starts with this heading. save_report uses it to find the
# report in the conversation.
REPORT_HEADING = "# Market research report"

# Report workflow: how many candidate companies are checked, and how many
# verified competitors go into the report.
REPORT_MAX_CANDIDATES = 8
REPORT_MAX_COMPETITORS = 5

# Human-in-the-loop: pause the report workflow so the user can approve or
# edit the competitor list before the detailed research starts.
REVIEW_COMPETITORS = True
# The most competitors a report can have after the user has added some.
REPORT_MAX_AFTER_REVIEW = 8

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
