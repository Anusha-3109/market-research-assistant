"""Tests for the input guard and the plain-language error messages."""

import pytest

from agent.guards import check_question, friendly_error


def test_a_normal_question_is_accepted():
    assert check_question("Is demand for meal kits rising in Germany?") is None


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_an_empty_question_is_turned_back(text):
    assert check_question(text) == "Type a question first."


def test_a_very_long_message_is_turned_back_with_its_length():
    problem = check_question("x" * 5000)

    assert "5,000 characters" in problem
    assert "under 2,000" in problem


def test_a_message_exactly_at_the_limit_is_accepted():
    assert check_question("x" * 2000) is None


@pytest.mark.parametrize("technical, expected", [
    ("Error code: 401 - Unauthorized: invalid api key", "API key was rejected"),
    ("Error code: 402 - Insufficient credits", "out of credit"),
    ("Error code: 429 - Rate limit exceeded", "too many requests"),
    ("Request timed out.", "took too long"),
    ("Connection error.", "could not reach the internet"),
])
def test_common_failures_are_explained_in_plain_words(technical, expected):
    assert expected in friendly_error(Exception(technical))


def test_an_unknown_failure_is_shown_but_kept_short():
    message = friendly_error(Exception("Unexpected: " + "y" * 1000))

    assert message.startswith("Something went wrong: Unexpected")
    assert len(message) < 340
