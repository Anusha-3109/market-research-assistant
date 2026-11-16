"""The tool that lets the chat agent run the report workflow.

The chat agent handles the conversation. When the user wants a report, it
calls this one tool, and the fixed workflow does the research.
"""

from functools import lru_cache

from langchain.tools import ToolRuntime, tool
from langgraph.errors import GraphInterrupt

from agent.citations import domain_of
from agent.config import MODEL_NAME, REVIEW_COMPETITORS, TEMPERATURE
from agent.countries import find_country
from agent.memory import UserContext
from agent.report.deps import default_deps
from agent.report.graph import build_report_graph

REPORT_TOOL_NAME = "create_market_report"
CANCELLED_MESSAGE = ("The report was cancelled at the competitor review. No "
                     "further research was done.")


@lru_cache(maxsize=8)
def report_graph(review: bool = False, model_name: str = MODEL_NAME,
                 temperature: float = TEMPERATURE):
    """Build each version of the workflow once and reuse it. There is one
    version per combination of settings."""
    return build_report_graph(default_deps(model_name, temperature), review=review)


def own_sites(final: dict) -> list[str]:
    """The sites that belong to the competitors in a finished report."""
    urls = [c.shop_url for c in final.get("competitors", [])]
    urls += [p.price_source for p in final.get("profiles", [])]
    return sorted({domain_of(url) for url in urls if url})


def run_report(product: str, country: str, idea: str, graph=None,
               review: bool = False, on_progress=None,
               model_name: str = MODEL_NAME,
               temperature: float = TEMPERATURE) -> tuple[str, dict]:
    """Run the workflow and return (text for the user, details).

    The details hold the report check result and the progress log, for the
    user interface to show next to the report.

    Args:
        on_progress: Called with each progress line as soon as a step
            finishes, so an interface can show the work live.
    """
    product, country = product.strip(), country.strip()
    if not product:
        return "I need to know which product or industry to research.", {}
    if find_country(country) is None:
        return (f"I could not recognise '{country}' as a country. Which single "
                f"country should the report cover?"), {}

    request = {"product": product, "country": country, "idea": idea.strip()}
    final: dict = {}
    try:
        # Two views of the same run: "updates" gives each step's result as it
        # finishes (for progress), "values" gives the whole state after each
        # step (the last one is the final result).
        workflow = graph or report_graph(review, model_name, temperature)
        for mode, chunk in workflow.stream(
                request, stream_mode=["updates", "values"]):
            if mode == "values":
                final = chunk
            elif on_progress:
                for step_output in chunk.values():
                    if isinstance(step_output, dict):
                        for line in step_output.get("log", []):
                            on_progress(line)
    except GraphInterrupt:
        # Not an error: the workflow paused for the user's review. Let it
        # pass up to the chat agent, which saves the state and stops.
        raise
    except Exception as error:  # a failed model call or network problem
        return (f"The report could not be produced because a step failed: "
                f"{error}. Please try again."), {}

    if final.get("cancelled"):
        return CANCELLED_MESSAGE, {"log": final.get("log", [])}
    if "report" not in final:
        return "The report could not be produced. Please try again.", {}
    return final["report"], {
        "problems": final.get("problems", []),
        "log": final.get("log", []),
        # For the app's source list: what each page is called, and which
        # sites are a competitor's own.
        "titles": final.get("titles", {}),
        "official": own_sites(final),
    }


# return_direct=True: the report goes to the user exactly as the workflow
# wrote it. Without it, the chat model would read the report and retype it,
# which costs time and can change figures or drop sources.
# response_format="content_and_artifact": the tool returns the text plus a
# second value (the details) that the model never sees.
@tool(REPORT_TOOL_NAME, return_direct=True, response_format="content_and_artifact")
def create_market_report(product: str, country: str, idea: str = "",
                         runtime: ToolRuntime[UserContext] = None) -> tuple[str, dict]:
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
    context = runtime.context if runtime else None
    chosen_review = getattr(context, "review_competitors", None)
    wants_review = REVIEW_COMPETITORS if chosen_review is None else chosen_review

    # The review pause needs a saved conversation to return to, which exists
    # only when the agent was given a checkpointer (a thread id is set).
    configurable = (runtime.config or {}).get("configurable", {}) if runtime else {}
    review = wants_review and bool(configurable.get("thread_id"))

    # Progress lines are sent through LangGraph's stream writer, so whoever
    # is streaming the chat agent receives them while the tool is running.
    writer = runtime.stream_writer if runtime else None
    on_progress = (lambda line: writer({"progress": line})) if writer else None
    return run_report(
        product, country, idea, review=review, on_progress=on_progress,
        model_name=getattr(context, "model_name", None) or MODEL_NAME,
        temperature=TEMPERATURE if getattr(context, "temperature", None) is None
        else context.temperature)
