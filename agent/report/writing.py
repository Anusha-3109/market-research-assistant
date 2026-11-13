"""Steps 8 and 9 of the report workflow: write the SWOT, then assemble and
check the report.

The SWOT is the one part the language model writes freely. It is given the
finished fact sections and told to reason only from them. If its answer is
incomplete, the graph sends it back to try once more.
"""

from agent.report.deps import Deps
from agent.report.render import fact_sections, render_report
from agent.report.state import ReportState, Swot
from agent.report_check import check_report

MAX_SWOT_ATTEMPTS = 2
MIN_POINTS = 2


def swot_is_complete(swot: Swot | None) -> bool:
    """True if each of the four lists has at least MIN_POINTS points."""
    if swot is None:
        return False
    return all(len(points) >= MIN_POINTS for points in
               (swot.strengths, swot.weaknesses, swot.opportunities, swot.threats))


def after_swot(state: ReportState) -> str:
    """Decide where the graph goes after the SWOT step: try again if the
    answer is incomplete and an attempt is left, otherwise carry on."""
    if not swot_is_complete(state.get("swot")) and state.get("swot_attempts", 0) < MAX_SWOT_ATTEMPTS:
        return "write_swot"
    return "assemble_report"


def make_writing_steps(deps: Deps) -> dict:

    def write_swot(state: ReportState) -> dict:
        """Step 8: the model's own analysis, based on the collected facts."""
        attempt = state.get("swot_attempts", 0) + 1
        facts = "\n\n".join(f"## {heading}\n{body}"
                            for heading, body in fact_sections(state).items())
        idea = state.get("idea") or "not described; write for a new entrant in this market"

        try:
            swot = deps.ask(
                Swot,
                f"Write a SWOT analysis for someone entering the "
                f"{state['product']} market in {state['country']}. Base every "
                f"point on the facts given; do not add facts, numbers or "
                f"company names that are not in them. Give {MIN_POINTS} to 4 "
                f"short points in each of the four lists. Strengths and "
                f"weaknesses are about the newcomer; opportunities and threats "
                f"are about the market. Do not give investment advice.",
                f"The user's business idea: {idea}\n\nFacts:\n\n{facts}",
            )
        except Exception:  # a failed model call counts as an incomplete answer
            swot = None

        complete = swot_is_complete(swot)
        return {
            "swot": swot,
            "swot_attempts": attempt,
            "log": [f"SWOT written (attempt {attempt})" if complete
                    else f"SWOT incomplete (attempt {attempt})"],
        }

    def assemble_report(state: ReportState) -> dict:
        """Step 9: build the report text and check it against the rules."""
        if not swot_is_complete(state.get("swot")):
            state = {**state, "swot": None}
        report = render_report(state)
        problems = check_report(report)
        return {
            "report": report,
            "problems": problems,
            "log": ["Report check: passed" if not problems
                    else f"Report check: {len(problems)} issues"],
        }

    return {"write_swot": write_swot, "assemble_report": assemble_report}
