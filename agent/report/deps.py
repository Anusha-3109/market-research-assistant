"""What the workflow needs from the outside world: a language model and a
web search.

They are passed in as plain functions. The real ones are created by
default_deps(); the tests pass in fakes, so the whole workflow can be tested
without the internet and without cost.
"""

from dataclasses import dataclass
from typing import Callable

from agent.config import MODEL_NAME
from agent.fallback import try_sources
from agent.models import make_model


@dataclass
class Deps:
    # ask(schema, instructions, material) -> an instance of schema.
    ask: Callable
    # search(query) -> list of results (title, url, content).
    search: Callable[[str], list[dict]]


def default_deps() -> Deps:
    """The real model and the real search, with their fallbacks."""
    # Imported here because tools.py is large and only needed at run time.
    from agent.tools import WEB_SEARCH_SOURCES

    model = make_model(MODEL_NAME)

    def ask(schema, instructions: str, material: str):
        # with_structured_output makes the model answer by "calling a
        # function" whose arguments are the schema's fields, so the reply
        # always has the right shape.
        structured = model.with_structured_output(schema, method="function_calling")
        return structured.invoke([
            {"role": "system", "content": instructions},
            {"role": "user", "content": material},
        ])

    def search(query: str) -> list[dict]:
        return try_sources(WEB_SEARCH_SOURCES, query).value or []

    return Deps(ask=ask, search=search)
