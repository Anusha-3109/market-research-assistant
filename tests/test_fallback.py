"""Tests for the fallback function, using fake sources (no internet)."""

import time

from agent.fallback import try_sources
from agent.sources import SourceError


def working(query):
    return [f"result for {query}"]


def broken(query):
    raise SourceError("service is down")


def empty(query):
    return []


def test_first_source_answers_and_the_backup_is_not_called():
    calls = []

    def backup(query):
        calls.append(query)
        return ["backup result"]

    result = try_sources([("Primary", working), ("Backup", backup)], "pizza")

    assert result.value == ["result for pizza"]
    assert result.used == "Primary"
    assert result.failures == []
    assert calls == []


def test_backup_answers_when_the_first_source_fails():
    result = try_sources([("Primary", broken), ("Backup", working)], "pizza")

    assert result.value == ["result for pizza"]
    assert result.used == "Backup"
    assert result.failures == [("Primary", "service is down")]


def test_backup_answers_when_the_first_source_returns_nothing():
    result = try_sources([("Primary", empty), ("Backup", working)], "pizza")

    assert result.used == "Backup"
    assert result.failures == [("Primary", "no results")]


def test_backup_answers_when_the_first_source_is_too_slow():
    def slow(query):
        time.sleep(1)
        return ["too late"]

    result = try_sources([("Primary", slow), ("Backup", working)], "pizza",
                         timeout=0.1)

    assert result.used == "Backup"
    assert result.failures == [("Primary", "timed out after 0.1s")]


def test_an_unexpected_bug_in_one_source_does_not_stop_the_next():
    def buggy(query):
        return {}["missing"]  # KeyError, not a SourceError

    result = try_sources([("Primary", buggy), ("Backup", working)], "pizza")

    assert result.used == "Backup"
    assert result.failures[0][0] == "Primary"


def test_when_every_source_fails_nothing_is_returned_and_each_reason_is_kept():
    result = try_sources([("Primary", broken), ("Backup", empty)], "pizza")

    assert not result.succeeded
    assert result.value is None
    assert result.failures == [("Primary", "service is down"),
                               ("Backup", "no results")]


def test_source_note_names_only_the_winner_when_nothing_failed():
    result = try_sources([("Primary", working)], "pizza")

    assert result.source_note() == "Source used: Primary"


def test_source_note_says_which_sources_were_unavailable():
    result = try_sources([("Primary", broken), ("Backup", working)], "pizza")

    assert result.source_note() == "Source used: Backup (Primary unavailable)"


def test_source_note_lists_every_reason_when_all_fail():
    result = try_sources([("Primary", broken), ("Backup", empty)], "pizza")

    assert result.source_note() == (
        "All sources unavailable: Primary (service is down), Backup (no results)"
    )
