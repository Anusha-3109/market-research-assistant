"""Connects the steps into a LangGraph graph.

    START
      |
  understand_request                      step 1
      |
  find_candidates                         step 2
      |
  verify_competitor   (one per candidate, in parallel)       step 3
      |
  select_competitors
      |
  review_competitors  (pause: the user approves or edits the list)
      |                 \\
      |                  cancelled --> END
      +-- research_competitor  (one per competitor)          steps 4, 5
      +-- research_market                                    step 6
      +-- research_news                                      step 7
      +-- research_trend                                     step 7
      |        (all of these run in parallel)
  collect_facts
      |
  write_swot  <--+   retried once if the answer is incomplete     step 8
      |----------+
  assemble_report                                                step 9
      |
     END

A graph has nodes (the steps) and edges (which step follows which). The
state is passed from node to node, and each node returns the fields it adds.
"""

from functools import wraps

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent import usage
from agent.report.deps import Deps, default_deps
from agent.report.research import make_research_steps
from agent.report.review import after_review, make_review_step
from agent.report.state import ReportState
from agent.report.steps import make_steps
from agent.report.writing import after_swot, make_writing_steps


def fan_out_to_verification(state: ReportState):
    """After step 2, start one verification branch per candidate.

    Returning a list of Send objects tells LangGraph to run the same node
    several times in parallel, each with its own input. If there are no
    candidates, go straight to the selection step.
    """
    candidates = state.get("candidates", [])
    if not candidates:
        return "select_competitors"

    return [
        Send("verify_competitor", {
            "candidate": candidate,
            "product": state["product"],
            "country": state["country"],
            "category_term": state["brief"].category_terms[0],
        })
        for candidate in candidates
    ]


def fan_out_to_research(state: ReportState):
    """After the competitors are settled, start all the fact-finding at
    once: one branch per competitor, plus the market, the news and the
    trend."""
    branches = [
        Send("research_competitor", {
            "competitor": competitor,
            "country": state["country"],
            "price_word": state["brief"].price_word,
        })
        for competitor in state.get("competitors", [])
    ]
    branches += [
        Send("research_market", state),
        Send("research_news", state),
        Send("research_trend", state),
    ]
    return branches


def research_or_stop(state: ReportState):
    """After the review: end the workflow if the user cancelled, otherwise
    start the research."""
    if after_review(state) == "cancelled":
        return END
    return fan_out_to_research(state)


RESEARCH_NODES = ["research_competitor", "research_market", "research_news",
                  "research_trend"]


def counted(step):
    """Wrap a step so that the model calls it makes are counted.

    The step runs inside usage.collecting(). Whatever was reported while it
    ran is added to the step's result under "usage", and the state adds the
    records of all steps together.
    """
    @wraps(step)
    def run(state):
        with usage.collecting() as calls:
            result = step(state)
        if calls and isinstance(result, dict):
            return {**result, "usage": [usage.to_record(usage.total(calls))]}
        return result

    return run


def build_report_graph(deps: Deps | None = None, review: bool = False):
    """Build and compile the report workflow.

    Args:
        deps: The model and data sources to use; the real ones by default.
        review: If True, the workflow pauses for the user to review the
            competitor list. A pause needs somewhere to save the state, so
            this only works when the workflow runs inside the chat agent,
            which has a checkpointer.
    """
    deps = deps or default_deps()
    steps = {**make_steps(deps), **make_research_steps(deps),
             **make_writing_steps(deps)}

    graph = StateGraph(ReportState)
    for name, function in steps.items():
        graph.add_node(name, counted(function))

    graph.add_edge(START, "understand_request")
    graph.add_edge("understand_request", "find_candidates")
    graph.add_conditional_edges("find_candidates", fan_out_to_verification,
                                ["verify_competitor", "select_competitors"])
    graph.add_edge("verify_competitor", "select_competitors")

    if review:
        graph.add_node("review_competitors", make_review_step(deps))
        graph.add_edge("select_competitors", "review_competitors")
        graph.add_conditional_edges("review_competitors", research_or_stop,
                                    RESEARCH_NODES + [END])
    else:
        graph.add_conditional_edges("select_competitors", fan_out_to_research,
                                    RESEARCH_NODES)

    for node in RESEARCH_NODES:
        graph.add_edge(node, "collect_facts")
    graph.add_edge("collect_facts", "write_swot")
    # A conditional edge that can point back at the node it came from: this
    # is how a graph expresses "try again".
    graph.add_conditional_edges("write_swot", after_swot,
                                ["write_swot", "assemble_report"])
    graph.add_edge("assemble_report", END)

    # checkpointer=True: when this graph runs inside the chat agent, it
    # saves its own progress in the agent's checkpointer. After a pause the
    # workflow continues from the review step and does not repeat the
    # searches before it.
    return graph.compile(checkpointer=True if review else None)
