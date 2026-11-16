"""Creates the agent once and keeps it for the whole server process."""

from dataclasses import dataclass

import streamlit as st

from agent.agent import build_agent
from agent.config import MODEL_NAME, TEMPERATURE
from agent.memory import open_memory


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
def _agent(model_name: str, temperature: float):
    """Build one agent per combination of settings, and reuse it."""
    checkpointer, store = _memory()
    return build_agent(model_name=model_name, temperature=temperature,
                       checkpointer=checkpointer, store=store)


def get_runtime(model_name: str = MODEL_NAME, temperature: float = TEMPERATURE) -> Runtime:
    """Return the agent for these settings, with the shared memory. Raises
    MissingKeyError if an API key is not set."""
    checkpointer, store = _memory()
    return Runtime(agent=_agent(model_name, temperature),
                   checkpointer=checkpointer, store=store)
