"""Creates the agent once and keeps it for the whole server process."""

from dataclasses import dataclass

import streamlit as st

from agent.agent import build_agent
from agent.memory import open_memory


@dataclass
class Runtime:
    agent: object
    checkpointer: object
    store: object


# cache_resource: Streamlit reruns the script on every click. Without the
# cache, each click would rebuild the agent and reopen the memory file.
@st.cache_resource(show_spinner=False)
def get_runtime() -> Runtime:
    """Open the memory file and build the agent. Raises MissingKeyError if
    an API key is not set."""
    checkpointer, store = open_memory()
    agent = build_agent(checkpointer=checkpointer, store=store)
    return Runtime(agent=agent, checkpointer=checkpointer, store=store)
