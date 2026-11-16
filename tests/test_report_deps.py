"""Tests for asking the model again when its answer has the wrong shape."""

import pytest
from pydantic import BaseModel, ValidationError

from agent.report.deps import ASK_ATTEMPTS, ask_with_retry


class Answer(BaseModel):
    reason: str


class Scripted:
    """Stands in for the model: each call returns the next reply, and a
    reply that does not fit the schema fails the way the real one does."""

    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.seen = []

    def invoke(self, messages):
        self.seen.append(messages)
        return Answer(**self.replies.pop(0))


def test_a_good_answer_is_returned_at_once():
    model = Scripted([{"reason": "sells coffee"}])

    assert ask_with_retry(model, "Judge.", "Material").reason == "sells coffee"
    assert len(model.seen) == 1


def test_an_answer_missing_a_field_is_asked_for_again_with_the_problem_named():
    model = Scripted([{}, {"reason": "second try"}])

    answer = ask_with_retry(model, "Judge.", "Material")

    assert answer.reason == "second try"
    assert "rejected" in model.seen[1][-1]["content"]
    assert "reason" in model.seen[1][-1]["content"]


def test_it_gives_up_after_the_last_attempt():
    model = Scripted([{}] * ASK_ATTEMPTS)

    with pytest.raises(ValidationError):
        ask_with_retry(model, "Judge.", "Material")
    assert len(model.seen) == ASK_ATTEMPTS
