"""Ratings of answers: thumbs up or down, given under each answer.

One rating per answer, kept in the long-term store under
("feedback", account id), keyed by the conversation and the answer's place
in it. Rating the same answer again replaces the rating; taking it back
removes it.

Besides the rating, a line keeps what is needed to learn from it later:
the question (cut short) and the settings the answer was written with.
A thumbs down can also keep what could be better: reasons and a comment.

The agent learns from the reasons: one that keeps coming up for an
account adds a fixed tip to that account's system prompt (tips_for_prompt).
"""

from datetime import datetime, timezone

UP, DOWN = 1, 0                 # the values st.feedback("thumbs") gives
NAMESPACE = "feedback"
LIMIT = 100_000
QUESTION_LIMIT = 300
COMMENT_LIMIT = 500
# What could be better, picked with a thumbs down. Shown in this order.
REASONS = ("wrong_facts", "missing_sources", "too_long", "too_short", "off_topic", "other")
# Learning from the ratings: a reason given in at least REPEATS of the
# account's last RECENT ratings adds its tip to that account's prompt.
RECENT, REPEATS = 10, 2
TIPS = {
    "wrong_facts": "Check each figure and date against its source, prefer the newest data, "
                   "and say which year a figure is from.",
    "missing_sources": "Back every figure and claim with a linked source.",
    "too_long": "Keep answers short: the direct answer first, then only the few points "
                "that matter most.",
    "too_short": "Give fuller answers: add the key figures and a short explanation, not only "
                 "the headline.",
    "off_topic": "Answer exactly the question asked; if it is unclear, ask one short question "
                 "first.",
}


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


def lessons(store, user_id: str) -> list[str]:
    """The reasons this account gave in at least REPEATS of its last RECENT
    ratings, in the order of REASONS. "Other" says nothing to act on, and
    "too long" with "too short" cancel each other out."""
    recent = ratings(store, user_id)[-RECENT:]
    counts = {reason: sum(reason in line.get("reasons", []) for line in recent) for reason in TIPS}
    found = [reason for reason in TIPS if counts[reason] >= REPEATS]
    if "too_long" in found and "too_short" in found:
        found = [reason for reason in found if reason not in ("too_long", "too_short")]
    return found


def tips_for_prompt(store, user_id: str) -> str:
    """The section added to this account's system prompt, or "".

    Only the fixed sentences in TIPS are added. A comment the user typed is
    never put in the prompt: it is the user's own text, and the prompt is
    no place for instructions from outside."""
    found = lessons(store, user_id) if store is not None else []
    if not found:
        return ""
    return ("\n## Learned from this user's ratings\n"
            "This user rated earlier answers down for the same reason more than once. "
            "Keep to these unless they ask for something else:\n"
            + "\n".join(f"- {TIPS[reason]}" for reason in found) + "\n")


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


def feedback_summary(lines: list[dict], answered: int, latest: int = 5) -> dict:
    """The figures the Feedback tab of the Admin page shows. `answered` is
    how many answers were written in the same time, from the usage log."""
    ups = sum(1 for line in lines if line["rating"] == UP)
    downs = [line for line in lines if line["rating"] == DOWN]
    counts = {reason: sum(reason in line.get("reasons", []) for line in downs) for reason in REASONS}
    reasons = dict(sorted(((reason, count) for reason, count in counts.items() if count),
                          key=lambda item: -item[1]))
    groups: dict[tuple[str, str], list[int]] = {}
    for line in lines:
        groups.setdefault((line["model"], line["style"]), []).append(line["rating"])
    by_setting = sorted(({"model": model, "style": style, "ratings": len(given),
                          "helpful": sum(given) / len(given)}
                         for (model, style), given in groups.items()),
                        key=lambda row: -row["ratings"])
    return {
        "ratings": len(lines),
        "up": ups,
        "down": len(downs),
        "helpful": ups / len(lines) if lines else None,
        "with_comment": sum(1 for line in downs if line.get("comment")),
        "reasons": reasons,
        "top_reason": next(iter(reasons), None),
        "answered": answered,
        "rated_share": min(len(lines) / answered, 1.0) if answered else None,
        "by_setting": by_setting,
        "latest_down": sorted(downs, key=lambda line: line["at"], reverse=True)[:latest],
    }
