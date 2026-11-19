"""Creates the agent once and keeps it for the whole server process."""

from dataclasses import dataclass

import streamlit as st

from agent.agent import build_agent
from agent.config import MODEL_NAME, TEMPERATURE
from agent.memory import open_memory
from agent.models import make_model


@dataclass
class Runtime:
    agent: object
    checkpointer: object
    store: object


# cache_resource: Streamlit reruns the script on every click. Without the
# cache, each click would rebuild the agent and reopen the memory file.
@st.cache_resource(show_spinner=False)
def _memory():
    """Open the memory file once. Every agent shares it, so changing the
    model in the settings keeps all conversations."""
    return open_memory()


@st.cache_resource(show_spinner=False, max_entries=8)
def _agent(model_name: str, temperature: float, disabled_tools: tuple = ()):
    """Build one agent per combination of settings, and reuse it."""
    checkpointer, store = _memory()
    return build_agent(model_name=model_name, temperature=temperature,
                       checkpointer=checkpointer, store=store, disabled_tools=disabled_tools)


# The assistant answers from the open report, so it is kept close to it.
SIDE_TEMPERATURE = 0.2


@st.cache_resource(show_spinner=False, max_entries=8)
def get_side_model(model_name: str = MODEL_NAME):
    """The model behind the assistant at the bottom right of the page
    (agent/side_assistant.py): the chosen model alone, without tools."""
    return make_model(model_name, SIDE_TEMPERATURE)


def get_store():
    """The long-term store alone. The sign-in screen uses it for the
    accounts. Opening it needs no API key and creates no agent."""
    return _memory()[1]


def get_runtime(model_name: str = MODEL_NAME, temperature: float = TEMPERATURE,
                disabled_tools: tuple = ()) -> Runtime:
    """Return the agent for these settings, with the shared memory. Raises
    MissingKeyError if an API key is not set."""
    checkpointer, store = _memory()
    return Runtime(agent=_agent(model_name, temperature, disabled_tools),
                   checkpointer=checkpointer, store=store)
