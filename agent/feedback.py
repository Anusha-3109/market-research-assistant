"""Ratings of answers: thumbs up or down, given under each answer.

One rating per answer, kept in the long-term store under
("feedback", account id), keyed by the conversation and the answer's place
in it. Rating the same answer again replaces the rating; taking it back
removes it.

Besides the rating, a line keeps what is needed to learn from it later:
the question (cut short) and the settings the answer was written with.
A thumbs down can also keep what could be better: reasons and a comment.
"""

from datetime import datetime, timezone

UP, DOWN = 1, 0                 # the values st.feedback("thumbs") gives
NAMESPACE = "feedback"
LIMIT = 100_000
QUESTION_LIMIT = 300
COMMENT_LIMIT = 500
# What could be better, picked with a thumbs down. Shown in this order.
REASONS = ("wrong_facts", "missing_sources", "too_long", "too_short", "off_topic", "other")


def _key(thread: str, index: int) -> str:
    return f"{thread}:{index}"


def rate(store, user_id: str, thread: str, index: int, rating: int | None, question: str,
         settings: dict, report: bool = False, when: datetime | None = None) -> None:
    """Save the rating of one answer, or remove it when `rating` is None."""
    if store is None:
        return
    namespace, key = (NAMESPACE, user_id), _key(thread, index)
    if rating is None:
        store.delete(namespace, key)
        return
    when = when or datetime.now(timezone.utc)
    store.put(namespace, key, {
        "at": when.isoformat(), "user": user_id, "thread": thread, "index": index,
        "rating": rating, "question": question[:QUESTION_LIMIT], "report": report,
        "model": settings.get("model", ""), "style": settings.get("style", ""),
        "length": settings.get("length", ""),
    })


def rating_line(store, user_id: str, thread: str, index: int) -> dict | None:
    """The saved rating of one answer with all it keeps, or None."""
    item = store.get((NAMESPACE, user_id), _key(thread, index)) if store is not None else None
    return dict(item.value) if item else None


def rating_of(store, user_id: str, thread: str, index: int) -> int | None:
    """The saved rating of one answer, or None."""
    line = rating_line(store, user_id, thread, index)
    return line["rating"] if line else None


def explain(store, user_id: str, thread: str, index: int, reasons: list[str],
            comment: str) -> None:
    """Keep what could be better with a thumbs down: the reasons picked
    (from REASONS) and a comment. Nothing is kept for an answer that is
    not rated down."""
    line = rating_line(store, user_id, thread, index)
    if line is None or line["rating"] != DOWN:
        return
    line["reasons"] = [reason for reason in REASONS if reason in reasons]
    line["comment"] = comment.strip()[:COMMENT_LIMIT]
    store.put((NAMESPACE, user_id), _key(thread, index), line)


def ratings(store, user_id: str | None, since: datetime | None = None) -> list[dict]:
    """The ratings of one account, or of every account (user_id None),
    oldest first, from `since` on."""
    if store is None:
        return []
    prefix = (NAMESPACE, user_id) if user_id else (NAMESPACE,)
    lines = [item.value for item in store.search(prefix, limit=LIMIT)]
    if since is not None:
        lines = [line for line in lines if datetime.fromisoformat(line["at"]) >= since]
    return sorted(lines, key=lambda line: line["at"])
