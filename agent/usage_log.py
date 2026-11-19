"""The usage log: one line per question, for the Dashboard and Admin pages.

A saved conversation already holds what each answer used. It does not hold
when a question was asked, how long the answer took, or the questions the
guard turned away or that failed. Those are written here, in the long-term
store, under ("usage", account id).

Nothing personal is kept: no question text, only what happened.
"""

from datetime import date, datetime, timedelta, timezone
from statistics import median
from uuid import uuid4

ANSWERED, TURNED_AWAY, ERROR, ASSISTANT = "answered", "turned_away", "error", "assistant"
# The kinds that count as a request: the assistant's quick chat does not.
REQUESTS = (ANSWERED, TURNED_AWAY, ERROR)
NAMESPACE = "usage"
LIMIT = 100_000


def record(store, user_id: str, kind: str, seconds: float | None = None, usage=None,
           tools: list[str] | None = None, report: bool = False, sources: int = 0,
           thread: str = "", error: str = "", when: datetime | None = None) -> None:
    """Write one line. `usage` is an agent.usage.Usage, or None."""
    if store is None:
        return
    when = when or datetime.now(timezone.utc)
    line = {"at": when.isoformat(), "user": user_id, "kind": kind, "seconds": seconds,
            "input_tokens": usage.input_tokens if usage else 0,
            "output_tokens": usage.output_tokens if usage else 0,
            "cost": usage.cost if usage else 0.0,
            "tools": list(tools or []), "report": report, "sources": sources,
            "thread": thread, "error": error[:200]}
    store.put((NAMESPACE, user_id), f"{when.isoformat()}-{uuid4().hex[:8]}", line)


def events(store, user_id: str | None, since: datetime | None = None) -> list[dict]:
    """The lines of one account, or of every account (user_id None), oldest
    first, from `since` on."""
    if store is None:
        return []
    prefix = (NAMESPACE, user_id) if user_id else (NAMESPACE,)
    lines = [item.value for item in store.search(prefix, limit=LIMIT)]
    if since is not None:
        lines = [line for line in lines if datetime.fromisoformat(line["at"]) >= since]
    return sorted(lines, key=lambda line: line["at"])


def summary(lines: list[dict]) -> dict:
    """The figures the Dashboard shows."""
    requests = [line for line in lines if line["kind"] in REQUESTS]
    answered = [line for line in lines if line["kind"] == ANSWERED]
    waits = [line["seconds"] for line in answered if line["seconds"] is not None]
    tools: dict[str, int] = {}
    for line in requests:
        for tool in line["tools"]:
            tools[tool] = tools.get(tool, 0) + 1
    return {
        "requests": len(requests),
        "answered": len(answered),
        "share_answered": len(answered) / len(requests) if requests else None,
        "median_seconds": median(waits) if waits else None,
        "tokens": sum(line["input_tokens"] + line["output_tokens"] for line in lines),
        "cost": sum(line["cost"] for line in lines),
        "reports": sum(1 for line in answered if line["report"]),
        "single": sum(1 for line in answered if not line["report"]),
        "sources": sum(line["sources"] for line in answered),
        "conversations": len({line["thread"] for line in answered if line["thread"]}),
        "turned_away": sum(1 for line in lines if line["kind"] == TURNED_AWAY),
        "errors": sum(1 for line in lines if line["kind"] == ERROR),
        "error_lines": [line for line in lines if line["kind"] == ERROR],
        "tools": dict(sorted(tools.items(), key=lambda item: -item[1])),
        "users": len({line["user"] for line in requests}),
    }


def per_day(lines: list[dict], last_day: date, days: int) -> list[dict]:
    """One row per day, the oldest first, with a row also for a quiet day."""
    rows = {last_day - timedelta(days=offset): {
        "day": last_day - timedelta(days=offset), ANSWERED: 0, TURNED_AWAY: 0, ERROR: 0,
        "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "waits_report": [], "waits_single": []}
        for offset in range(days)}
    for line in lines:
        row = rows.get(datetime.fromisoformat(line["at"]).date())
        if row is None:
            continue
        if line["kind"] in REQUESTS:
            row[line["kind"]] += 1
        row["input_tokens"] += line["input_tokens"]
        row["output_tokens"] += line["output_tokens"]
        row["cost"] += line["cost"]
        if line["kind"] == ANSWERED and line["seconds"] is not None:
            row["waits_report" if line["report"] else "waits_single"].append(line["seconds"])
    return [rows[day] for day in sorted(rows)]
