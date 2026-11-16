"""Human-in-the-loop: the two points where the agent stops for the user.

1. "competitor_review": inside the report workflow, after the competitors
   are verified. The user approves, edits or cancels.
2. "save_approval": before the save_report tool writes a file. The user
   approves, changes the title or rejects.

Both use the same LangGraph mechanism, an interrupt, but they are set up
differently: the first is an interrupt() call written into the workflow,
the second is LangChain's ready-made HumanInTheLoopMiddleware. This module
gives the rest of the app one simple way to see a pause and answer it.
"""

from dataclasses import dataclass

from agent.report.review import REVIEW_KIND
from agent.tools import safe_filename

SAVE_KIND = "save_approval"
SAVE_TOOL = "save_report"

# The setting handed to HumanInTheLoopMiddleware: pause before save_report
# and allow these three answers.
SAVE_APPROVAL_CONFIG = {
    SAVE_TOOL: {"allowed_decisions": ["approve", "edit", "reject"]},
}


@dataclass
class Pause:
    """The agent has stopped and is waiting for the user.

    kind: "competitor_review" or "save_approval".
    data: what to show the user.
    """

    kind: str
    data: dict


def read_pause(value) -> Pause | None:
    """Turn the raw value of an interrupt into a Pause, or None if it is
    not one of ours."""
    if not isinstance(value, dict):
        return None
    if value.get("kind") == REVIEW_KIND:
        return Pause(REVIEW_KIND, value)

    # The middleware's request lists the tool calls waiting for approval.
    for request in value.get("action_requests", []):
        if request.get("name") == SAVE_TOOL:
            title = str(request.get("args", {}).get("title", ""))
            return Pause(SAVE_KIND, {"title": title,
                                     "filename": f"reports/{safe_filename(title)}"})
    return None


# --- building the answer that resumes the run ---------------------------------------------

def review_answer(action: str, remove: list[str] | None = None,
                  add: list[str] | None = None) -> dict:
    """The answer to a competitor review: "approve", "edit" or "cancel"."""
    if action == "edit":
        return {"action": "edit", "remove": remove or [], "add": add or []}
    return {"action": action}


def save_answer(action: str, title: str = "") -> dict:
    """The answer to a save approval, in the shape the middleware expects:
    "approve", "reject", or "edit" with a new title."""
    if action == "edit":
        decision = {"type": "edit",
                    "edited_action": {"name": SAVE_TOOL, "args": {"title": title}}}
    elif action == "reject":
        decision = {"type": "reject",
                    "message": "The user declined to save the report. Do not "
                               "try again unless they ask."}
    else:
        decision = {"type": "approve"}
    return {"decisions": [decision]}


# --- reading a typed answer (terminal chat) ---------------------------------------------------

def parse_review_reply(reply: str, names: list[str]) -> dict:
    """Understand a typed answer to the competitor review.

    Accepted: "approve", "cancel", "remove 2,4", "add Marley Spoon", or
    several parts joined with ";" such as "remove 4; add Marley Spoon".
    A company to remove can be given by its number in the list or its name.
    Anything not understood counts as approve.
    """
    reply = reply.strip()
    if reply.lower() in ("cancel", "stop", "no"):
        return review_answer("cancel")

    remove, add = [], []
    for part in reply.split(";"):
        word, _, rest = part.strip().partition(" ")
        items = [item.strip() for item in rest.split(",") if item.strip()]
        if word.lower() == "remove":
            for item in items:
                if item.isdigit() and 1 <= int(item) <= len(names):
                    remove.append(names[int(item) - 1])
                elif not item.isdigit():
                    remove.append(item)
        elif word.lower() == "add":
            add += items

    if remove or add:
        return review_answer("edit", remove, add)
    return review_answer("approve")


def parse_save_reply(reply: str) -> dict:
    """Understand a typed answer to the save approval.

    Accepted: "approve", "reject", or "title <new title>". Anything not
    understood counts as reject, because saving writes a file.
    """
    reply = reply.strip()
    word, _, rest = reply.partition(" ")
    if word.lower() in ("approve", "yes", "y", "ok"):
        return save_answer("approve")
    if word.lower() == "title" and rest.strip():
        return save_answer("edit", rest.strip())
    return save_answer("reject")
