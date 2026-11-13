"""Connects the steps into a LangGraph graph.

    START
      |
  understand_request      step 1
      |
  find_candidates         step 2
      |
  (one branch per candidate, run in parallel)
  verify_competitor       step 3
      |
  select_competitors
      |
     END

A graph has nodes (the steps) and edges (which step follows which). The
state is passed from node to node, and each node returns the fields it adds.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent.report.deps import Deps, default_deps
from agent.report.state import ReportState
from agent.report.steps import make_steps


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


def build_report_graph(deps: Deps | None = None):
    """Build and compile the report workflow."""
    steps = make_steps(deps or default_deps())

    graph = StateGraph(ReportState)
    for name, function in steps.items():
        graph.add_node(name, function)

    graph.add_edge(START, "understand_request")
    graph.add_edge("understand_request", "find_candidates")
    graph.add_conditional_edges("find_candidates", fan_out_to_verification,
                                ["verify_competitor", "select_competitors"])
    graph.add_edge("verify_competitor", "select_competitors")
    graph.add_edge("select_competitors", END)

    return graph.compile()
