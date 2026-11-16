"""What the workflow needs from the outside world: a language model and a
web search.

They are passed in as plain functions. The real ones are created by
default_deps(); the tests pass in fakes, so the whole workflow can be tested
without the internet and without cost.
"""

from dataclasses import dataclass
from typing import Callable

from agent.config import MODEL_NAME, TEMPERATURE
from agent.fallback import try_sources
from agent.models import make_model


@dataclass
class Deps:
    # ask(schema, instructions, material) -> an instance of schema.
    ask: Callable
    # search(query) -> list of results (title, url, content).
    search: Callable[[str], list[dict]]
    # news(query) -> list of recent news results.
    news: Callable[[str], list[dict]]
    # read_page(url) -> the page's text, or None if it cannot be read.
    read_page: Callable[[str], str | None]
    # financials(company) -> text with public figures, or None if not found.
    financials: Callable[[str], str | None]
    # trend(term, country) -> a TrendSeries, or None if there is no data.
    trend: Callable


def default_deps(model_name: str = MODEL_NAME,
                 temperature: float = TEMPERATURE) -> Deps:
    """The real model and the real search, with their fallbacks."""
    # Imported here because tools.py is large and only needed at run time.
    from agent.sources import webpage
    from agent.tools import (
        NEWS_SOURCES,
        PAGE_SOURCES,
        TREND_SOURCES,
        WEB_SEARCH_SOURCES,
        get_company_financials,
    )

    model = make_model(model_name, temperature)

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

    def news(query: str) -> list[dict]:
        return try_sources(NEWS_SOURCES, query).value or []

    def read_page(url: str) -> str | None:
        try:
            webpage.check_url(url)
        except webpage.UnsafeUrlError:
            return None
        return try_sources(PAGE_SOURCES, url).value

    def financials(company: str) -> str | None:
        # Reuses the chat agent's tool, including its brand-name retry.
        text = get_company_financials.invoke({"company": company})
        return text if text.startswith("Source used") else None

    def trend(term: str, country):
        return try_sources(TREND_SOURCES, term, country).value

    return Deps(ask=ask, search=search, news=news, read_page=read_page,
                financials=financials, trend=trend)
