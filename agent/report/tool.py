"""The tool that lets the chat agent run the report workflow.

The chat agent handles the conversation. When the user wants a report, it
calls this one tool, and the fixed workflow does the research.
"""

from functools import lru_cache

from langchain.tools import tool

from agent.countries import find_country
from agent.report.graph import build_report_graph

REPORT_TOOL_NAME = "create_market_report"


@lru_cache(maxsize=1)
def report_graph():
    """Build the workflow once and reuse it."""
    return build_report_graph()


def run_report(product: str, country: str, idea: str, graph=None) -> tuple[str, dict]:
    """Run the workflow and return (text for the user, details).

    The details hold the report check result and the progress log, for the
    user interface to show next to the report.
    """
    product, country = product.strip(), country.strip()
    if not product:
        return "I need to know which product or industry to research.", {}
    if find_country(country) is None:
        return (f"I could not recognise '{country}' as a country. Which single "
                f"country should the report cover?"), {}

    try:
        final = (graph or report_graph()).invoke(
            {"product": product, "country": country, "idea": idea.strip()})
    except Exception as error:  # a failed model call or network problem
        return (f"The report could not be produced because a step failed: "
                f"{error}. Please try again."), {}

    return final["report"], {"problems": final.get("problems", []),
                             "log": final.get("log", [])}


# return_direct=True: the report goes to the user exactly as the workflow
# wrote it. Without it, the chat model would read the report and retype it,
# which costs time and can change figures or drop sources.
# response_format="content_and_artifact": the tool returns the text plus a
# second value (the details) that the model never sees.
@tool(REPORT_TOOL_NAME, return_direct=True, response_format="content_and_artifact")
def create_market_report(product: str, country: str, idea: str = "") -> tuple[str, dict]:
    """Research a market and write the full six-section market research
    report: market overview, competitors, pricing, trends, SWOT analysis and
    references.

    Use this whenever the user asks for a market research report. It takes
    about a minute. Only call it when you know both the product and the
    country; if the country is missing, ask the user first.

    Args:
        product: The product or industry, for example "healthy meal delivery".
        country: One country, in English, for example "Germany".
        idea: The user's own business idea in their words, if they described
            one. Leave empty otherwise.
    """
    return run_report(product, country, idea)
