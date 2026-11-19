"""Ratings sent to LangSmith, onto the trace of the answer they rate.

With tracing on (agent/tracing.py), each answer's run has a known id
(agent.agent.run_config). A rating becomes feedback on that run, named
"user_rating": 1 for a thumbs up, 0 for a thumbs down, with the reasons as
its value and the comment as its comment. In LangSmith the traces can then
be filtered by it, to read the answers people rated down.

One rating per answer: each feedback has an id made from the run id, so
rating again replaces it, and taking the rating back removes it.

Sending happens in the background and may fail (no network, LangSmith
down): the rating is still saved in the app, and the user sees nothing.
"""

import logging
import threading
from uuid import NAMESPACE_URL, UUID, uuid5

from agent.tracing import tracing_is_on

KEY = "user_rating"
log = logging.getLogger(__name__)


def feedback_id(run_id: str) -> UUID:
    """The id of the one rating a run can have."""
    return uuid5(NAMESPACE_URL, f"markavi-rating:{run_id}")


def send_rating(run_id: str | None, rating: int | None, reasons: list[str], comment: str,
                client=None, env=None) -> bool:
    """Send the rating of one run's answer, or remove it when rating is None.
    Returns True if it was sent."""
    if not run_id or not tracing_is_on(env):
        return False
    try:
        if client is None:
            from langsmith import Client
            client = Client()
        try:
            client.delete_feedback(feedback_id(run_id))     # the earlier rating, if any
        except Exception:                                 # there was none
            pass
        if rating is not None:
            client.create_feedback(run_id, KEY, score=rating, value=",".join(reasons) or None,
                                   comment=comment or None, feedback_id=feedback_id(run_id))
        return True
    except Exception as error:
        log.warning("Could not send the rating to LangSmith: %s", error)
        return False


def send_in_background(run_id: str | None, rating: int | None, reasons: list[str],
                       comment: str) -> None:
    """send_rating() without making the page wait for LangSmith."""
    if run_id and tracing_is_on():
        threading.Thread(target=send_rating, args=(run_id, rating, reasons, comment),
                         daemon=True).start()
