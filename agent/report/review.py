"""Human review of the competitor list.

After the competitors are verified, the workflow stops and shows the list to
the user, who can approve it, remove companies, add companies or cancel the
report. Choosing competitors is where the automatic steps are weakest, and
the user knows their market, so this is where a person's judgement is worth
the most.

The pause is LangGraph's interrupt(): it saves the workflow's state through
the checkpointer and hands control back to the caller. When the user has
answered, the workflow continues from this step with their answer.
"""

from langgraph.types import interrupt

from agent.config import REPORT_MAX_AFTER_REVIEW
from agent.report.deps import Deps
from agent.report.state import Competitor, ReportState
from agent.report.steps import clean_url, is_own_site, name_key

REVIEW_KIND = "competitor_review"


def review_request(state: ReportState) -> dict:
    """What the user is shown: the chosen competitors, the verified ones
    that were left out, and the ones that were dropped with the reason."""
    chosen = state.get("competitors", [])
    chosen_keys = {name_key(c.name) for c in chosen}
    return {
        "kind": REVIEW_KIND,
        "product": state["product"],
        "country": state["country"],
        "competitors": [{"name": c.name, "website": c.shop_url, "offer": c.offer}
                        for c in chosen],
        "left_out": [c.name for c in state.get("verified", [])
                     if name_key(c.name) not in chosen_keys],
        "dropped": [{"name": r.name, "reason": r.reason}
                    for r in state.get("rejected", [])],
    }


def find_added_company(name: str, state: ReportState, deps: Deps) -> Competitor | None:
    """Build a competitor record for a company the user asked to add.

    A company the workflow had already verified is reused. Otherwise one
    search looks for the company's own website; any page that mentions it
    is kept as the evidence link. The user's word is trusted on whether it
    is a competitor, so no verification is run. Returns None only if the
    search finds nothing at all, because the report needs a source link.
    """
    for known in state.get("verified", []):
        if name_key(known.name) == name_key(name):
            return known

    results = deps.search(f"{name} {state['country']}")
    if not results:
        return None
    urls = [clean_url(r.get("url", "")) for r in results if r.get("url")]
    own_site = next((url for url in urls if is_own_site(name, url)), "")
    return Competitor(name=name, shop_url=own_site, evidence_url=own_site or urls[0],
                      reason="added by the user", offer="Added by you")


def apply_review(state: ReportState, decision: dict, deps: Deps) -> dict:
    """Turn the user's decision into the new competitor list.

    decision is {"action": "approve"}, {"action": "cancel"} or
    {"action": "edit", "remove": [names], "add": [names]}.
    """
    action = (decision or {}).get("action", "approve")
    competitors = list(state.get("competitors", []))

    if action == "cancel":
        return {"cancelled": True, "log": ["Review: the user cancelled the report"]}
    if action != "edit":
        return {"log": ["Review: the user approved the competitor list"]}

    log = []
    removed = {name_key(name) for name in decision.get("remove", [])}
    kept = [c for c in competitors if name_key(c.name) not in removed]
    for competitor in competitors:
        if name_key(competitor.name) in removed:
            log.append(f"Review: removed {competitor.name}")

    present = {name_key(c.name) for c in kept}
    for name in decision.get("add", []):
        name = " ".join(str(name).split())
        if not name or name_key(name) in present:
            continue
        if len(kept) >= REPORT_MAX_AFTER_REVIEW:
            log.append(f"Review: {name} not added (limit of {REPORT_MAX_AFTER_REVIEW} competitors)")
            continue
        added = find_added_company(name, state, deps)
        if added is None:
            log.append(f"Review: {name} not added (no information found about it)")
            continue
        kept.append(added)
        present.add(name_key(name))
        log.append(f"Review: added {added.name}")

    return {"competitors": kept, "log": log or ["Review: no changes made"]}


def after_review(state: ReportState) -> str:
    """Where the graph goes after the review: stop if cancelled."""
    return "cancelled" if state.get("cancelled") else "continue"


def make_review_step(deps: Deps):

    def review_competitors(state: ReportState) -> dict:
        """Pause for the user's decision on the competitor list.

        interrupt() stops the workflow here and returns its argument to the
        caller. When the run is resumed, this function runs again from the
        top and interrupt() returns the user's answer instead of pausing.
        """
        if not state.get("competitors") and not state.get("verified"):
            return {"log": ["Review skipped: no competitors were found"]}
        decision = interrupt(review_request(state))
        return apply_review(state, decision, deps)

    return review_competitors
