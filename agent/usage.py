"""Token usage and cost.

Every call to a language model reads some tokens (the instructions and the
conversation so far) and writes some (the reply). A token is about three
quarters of a word. The model service, OpenRouter, reports both numbers for
each call, together with what the call cost in US dollars.

The cost shown in the app is that reported cost. It is not worked out from
a price list, which would go out of date whenever a model's price changes.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from math import floor, log10

from langchain_core.messages import AIMessage


@dataclass(frozen=True)
class Usage:
    """What a number of model calls used.

    calls:         how many calls.
    input_tokens:  tokens read by the model.
    output_tokens: tokens written by the model.
    cost:          the cost in US dollars of the calls that had one.
    priced_calls:  how many of the calls the service gave a cost for.
    """

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    priced_calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.calls + other.calls,
                     self.input_tokens + other.input_tokens,
                     self.output_tokens + other.output_tokens,
                     self.cost + other.cost,
                     self.priced_calls + other.priced_calls)


def usage_of(message: AIMessage) -> Usage:
    """What one reply of the model used. A message without figures (one
    written by code, or by a fake model in a test) counts as nothing."""
    tokens = message.usage_metadata
    if not tokens:
        return Usage()
    cost = (message.response_metadata.get("token_usage") or {}).get("cost")
    return Usage(calls=1,
                 input_tokens=tokens.get("input_tokens", 0),
                 output_tokens=tokens.get("output_tokens", 0),
                 cost=cost or 0.0,
                 priced_calls=0 if cost is None else 1)


# --- how it is worded on the page ------------------------------------------------------

def format_cost(cost: float) -> str:
    """A cost in US dollars. One answer costs a fraction of a cent, so a
    small amount keeps enough digits to mean something: $0.0005, not $0.00."""
    if cost == 0:
        return "$0"
    if cost >= 1:
        return f"${cost:,.2f}"
    # Two digits from the first one that is not zero, and at least cents.
    digits = max(2, 1 - floor(log10(cost)))
    text = f"{cost:.{digits}f}"
    whole, decimals = text.split(".")
    decimals = decimals.rstrip("0").ljust(2, "0")
    return f"${whole}.{decimals}"


def summary(usage: Usage, partial: bool = False) -> str:
    """One line for the page: "1,240 tokens · $0.0005". Empty if no model
    was called.

    A price is never made up. If the service gave no cost for some calls,
    the line says so. partial=True is for a report written before costs
    were recorded: only the chat model's part of it is known.
    """
    if usage.calls == 0:
        return ""
    line = f"{usage.total_tokens:,} tokens · "
    if usage.priced_calls == 0:
        line += "cost not reported"
    else:
        line += format_cost(usage.cost)
        unpriced = usage.calls - usage.priced_calls
        if unpriced:
            line += f" ({unpriced} of {usage.calls} calls had no reported cost)"
    if partial:
        line += " (the report's own calls were not recorded)"
    return line


def details(usage: Usage) -> str:
    """A longer explanation of the same figures, shown on request."""
    calls = "1 model call" if usage.calls == 1 else f"{usage.calls} model calls"
    return (f"{calls}. {usage.input_tokens:,} tokens read, "
            f"{usage.output_tokens:,} tokens written. A token is about three "
            "quarters of a word. The cost is what the model service reported, "
            "in US dollars. Web searches are billed separately and are not "
            "included.")


def total(records: list[dict] | None) -> Usage:
    """Add up usage that was stored as plain records (see to_record)."""
    result = Usage()
    for record in records or []:
        result += Usage(**record)
    return result


def to_record(usage: Usage) -> dict:
    """Usage as a plain dictionary, for storing in a saved state. A saved
    state should hold simple values only."""
    return asdict(usage)


# --- counting calls that are not messages in the conversation ---------------------------
#
# The chat agent's calls are counted by reading the saved conversation: each
# reply of the model is a message that carries its own figures.
#
# The report workflow is different. It asks its model many separate
# questions and keeps only the answers. So each step of the workflow runs
# inside collecting(), and whoever calls the model reports the call with
# record(). The step then stores what was collected in the report's state.
#
# A context variable holds the list being filled. It is separate for each
# step that runs, also when several steps run at the same time.

# Under this name a user's message carries what the background call that
# read it used (see capture_profile in agent/agent.py).
BACKGROUND_KEY = "background_usage"

_collected: ContextVar[list[dict] | None] = ContextVar("collected_usage", default=None)


def record(message: AIMessage) -> None:
    """Report one model call. Outside collecting() this does nothing, so it
    is safe to call from anywhere."""
    calls = _collected.get()
    if calls is not None:
        calls.append(to_record(usage_of(message)))


@contextmanager
def collecting():
    """Collect the model calls reported while the block runs. Gives the
    list they are added to."""
    calls: list[dict] = []
    token = _collected.set(calls)
    try:
        yield calls
    finally:
        _collected.reset(token)


def answer_of(reply):
    """Take the answer out of a reply that has a fixed shape, and report
    the call.

    A model asked with include_raw=True returns the answer together with
    the raw message, which carries the tokens and the cost of the call. The
    call is reported whether or not the answer fits the shape: a rejected
    answer was paid for as well.
    """
    if not (isinstance(reply, dict) and "raw" in reply):
        return reply            # a plain answer, as a simple fake model gives
    record(reply["raw"])
    if reply.get("parsing_error"):
        raise reply["parsing_error"]
    return reply["parsed"]
