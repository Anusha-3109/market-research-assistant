"""Tests for whose conversation is whose.

With accounts on, each conversation belongs to the account that asked its
first question. The agent is a fake one with real, temporary memory.
"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from agent import memory, session
from agent.agent import stream_steps
from agent.memory import UserContext
from agent.tools import reports_folder
from tests.test_app import make_runtime

ANNA, BEN = "u-anna", "u-ben"


@pytest.fixture
def runtime(tmp_path):
    runtime = make_runtime(tmp_path, [AIMessage(f"Answer {n}.") for n in range(1, 9)])
    yield runtime
    runtime.checkpointer.conn.close()


def ask(runtime, thread_id: str, question: str, user_id: str | None = None) -> None:
    """Ask a question in a conversation. With a user id, the conversation
    is first claimed for that user, as the page does."""
    if user_id:
        session.claim_conversation(runtime.store, thread_id, user_id)
    list(stream_steps(runtime.agent, question, thread_id,
                      context=UserContext(user_id=user_id or memory.DEFAULT_USER)))


def titles(runtime, user_id: str | None = None) -> list[str]:
    listed = session.list_conversations(runtime.agent, runtime.checkpointer,
                                        store=runtime.store, user_id=user_id)
    return sorted(conversation.title for conversation in listed)


# --- whose conversation ------------------------------------------------------------------------

def test_a_conversation_belongs_to_whoever_claimed_it(runtime):
    session.claim_conversation(runtime.store, "t1", ANNA)

    assert session.owner_of(runtime.store, "t1") == ANNA


def test_a_conversation_nobody_claimed_has_no_owner(runtime):
    assert session.owner_of(runtime.store, "t1") is None


def test_a_claimed_conversation_cannot_be_claimed_by_someone_else(runtime):
    session.claim_conversation(runtime.store, "t1", ANNA)

    session.claim_conversation(runtime.store, "t1", BEN)

    assert session.owner_of(runtime.store, "t1") == ANNA


# --- the list in the sidebar ---------------------------------------------------------------------

def test_each_account_lists_only_its_own_conversations(runtime):
    ask(runtime, "t1", "Anna's question", ANNA)
    ask(runtime, "t2", "Ben's question", BEN)
    ask(runtime, "t3", "Anna's second question", ANNA)

    assert titles(runtime, ANNA) == ["Anna's question", "Anna's second question"]
    assert titles(runtime, BEN) == ["Ben's question"]


def test_without_accounts_every_conversation_is_listed(runtime):
    ask(runtime, "t1", "First question")
    ask(runtime, "t2", "Second question")

    assert titles(runtime) == ["First question", "Second question"]


def test_another_accounts_many_conversations_do_not_push_yours_off_the_list(runtime, monkeypatch):
    monkeypatch.setattr(session, "MAX_CONVERSATIONS", 2)
    ask(runtime, "t1", "Anna's question", ANNA)
    ask(runtime, "t2", "Ben's first", BEN)
    ask(runtime, "t3", "Ben's second", BEN)

    assert titles(runtime, ANNA) == ["Anna's question"]


# --- opening a conversation by its address --------------------------------------------------------

def test_you_may_open_your_own_conversation(runtime):
    ask(runtime, "t1", "Anna's question", ANNA)

    assert session.may_open(runtime.agent, runtime.store, "t1", ANNA)


def test_you_may_not_open_another_accounts_conversation(runtime):
    ask(runtime, "t1", "Anna's question", ANNA)

    assert not session.may_open(runtime.agent, runtime.store, "t1", BEN)


def test_an_empty_conversation_is_open_to_anyone(runtime):
    assert session.may_open(runtime.agent, runtime.store, "brand-new", BEN)


def test_a_conversation_with_messages_and_no_owner_is_closed_to_accounts(runtime):
    ask(runtime, "t1", "A question from before there were accounts")

    assert not session.may_open(runtime.agent, runtime.store, "t1", BEN)


# --- what was there before there were accounts ------------------------------------------------------

def test_the_first_account_takes_over_what_was_there_before(runtime):
    ask(runtime, "t1", "An old question")
    memory.save_preference(runtime.store, memory.DEFAULT_USER, "region", "Portugal")

    assert session.adopt_existing(runtime.store, runtime.checkpointer, ANNA) is True

    assert titles(runtime, ANNA) == ["An old question"]
    assert memory.load_profile(runtime.store, ANNA) == {"region": "Portugal"}
    # Nothing is left behind for an app without accounts to show.
    assert memory.load_profile(runtime.store, memory.DEFAULT_USER) == {}


def test_only_the_first_account_takes_over(runtime):
    ask(runtime, "t1", "An old question")
    session.adopt_existing(runtime.store, runtime.checkpointer, ANNA)

    assert session.adopt_existing(runtime.store, runtime.checkpointer, BEN) is False

    assert titles(runtime, BEN) == []
    assert session.owner_of(runtime.store, "t1") == ANNA


def test_taking_over_happens_once_even_if_nothing_was_there(runtime):
    session.adopt_existing(runtime.store, runtime.checkpointer, ANNA)
    ask(runtime, "t1", "A stray question nobody claimed")

    assert session.adopt_existing(runtime.store, runtime.checkpointer, ANNA) is False
    assert session.owner_of(runtime.store, "t1") is None


def test_taking_over_leaves_claimed_conversations_alone(runtime):
    ask(runtime, "t1", "Ben's question", BEN)

    session.adopt_existing(runtime.store, runtime.checkpointer, ANNA)

    assert session.owner_of(runtime.store, "t1") == BEN


# --- saved reports ------------------------------------------------------------------------------------

def test_each_account_saves_reports_in_its_own_folder():
    base = Path("reports")

    assert reports_folder(base, ANNA) == base / "u-anna"
    assert reports_folder(base, BEN) == base / "u-ben"


def test_without_accounts_reports_go_straight_into_the_reports_folder():
    assert reports_folder(Path("reports"), memory.DEFAULT_USER) == Path("reports")
