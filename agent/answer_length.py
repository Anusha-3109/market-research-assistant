"""The "Maximum answer length" setting.

A hard cap on how much the model may write in one chat answer, counted in
tokens (a token is about three quarters of a word). It is the model
service's own limit, known there as "max tokens".

This is different from the Concise answer style. A style asks the model to
write briefly and the model decides how. The limit is enforced by the model
service: when it is reached, the answer simply stops.

It applies to chat answers only. A report is built from several structured
answers of the model, and a cut-off one would break the report, so the
report workflow never uses the limit.
"""

from langchain_core.messages import AIMessage

# Added under an answer that the limit cut off. Without it, an answer that
# stops in the middle of a sentence looks like a fault of the app.
CUT_OFF_NOTE = "*This answer was cut off by the maximum answer length chosen in Settings.*"


def answer_limit(context) -> int | None:
    """The limit chosen by the user, or None for no limit. A setting is
    never trusted to hold a sensible value."""
    limit = getattr(context, "max_answer_tokens", None)
    return limit if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0 else None


def was_cut_off(message: AIMessage) -> bool:
    """True if the model stopped because it reached the limit, and not
    because it had finished. The model service reports which it was."""
    return message.response_metadata.get("finish_reason") == "length"


def is_an_answer(message: AIMessage) -> bool:
    """True if the message is text for the user, and not a step on the way
    there (a request for a tool) or an empty reply."""
    return (not message.tool_calls and not message.invalid_tool_calls
            and isinstance(message.content, str) and bool(message.content.strip()))


def with_cut_off_note(message: AIMessage) -> AIMessage:
    """The message with the note added under its text."""
    return message.model_copy(update={"content": f"{message.content.rstrip()}\n\n{CUT_OFF_NOTE}"})
