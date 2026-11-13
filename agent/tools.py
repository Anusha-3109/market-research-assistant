"""Tools the agent can call.

A tool is a normal Python function with the @tool decorator. The model never
runs it. The model only asks for it by name with arguments; LangChain runs
the function and passes the returned text back to the model.
"""

from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from agent.config import SEARCH_MAX_RESULTS


def format_results(results: list[dict]) -> str:
    """Turn raw search results into numbered text the model can cite from."""
    if not results:
        return "No results found. Try a different or more specific query."

    blocks = []
    for number, item in enumerate(results, start=1):
        title = item.get("title") or "Untitled"
        url = item.get("url") or "no url"
        snippet = (item.get("content") or "").strip()
        blocks.append(f"[{number}] {title}\nURL: {url}\n{snippet}")
    return "\n\n".join(blocks)


@tool
def web_search(query: str) -> str:
    """Search the web for current information about a market, industry,
    competitor, price or trend.

    Use this whenever you need facts. Each result has a title, a URL and a
    short extract. Cite the URL when you use a fact from a result.

    Args:
        query: A focused search query of 3 to 10 words that includes the
            country or region, for example "meal kit delivery competitors
            Germany".
    """
    try:
        search = TavilySearch(max_results=SEARCH_MAX_RESULTS)
        response = search.invoke({"query": query})
    except Exception as error:  # network problem, bad key, rate limit
        return f"Search failed: {error}. Try again or use a different query."

    if isinstance(response, dict) and response.get("error"):
        return f"Search failed: {response['error']}."

    results = response.get("results", []) if isinstance(response, dict) else []
    return format_results(results)


TOOLS = [web_search]
