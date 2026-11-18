"""Tests for user accounts: creating one, signing in, and the wait after
too many wrong tries.

The accounts are kept in the same store as the agent's long-term memory.
The tests use a store held in RAM and made-up people.
"""

import pytest
from langgraph.store.memory import InMemoryStore

from agent import accounts
from agent.accounts import AccountError

PASSWORD = "correct horse battery"


@pytest.fixture
def store():
    return InMemoryStore()


def everything_stored(store) -> str:
    """All that the store holds, as text."""
    items = [item for namespace in store.list_namespaces()
             for item in store.search(namespace)]
    return " ".join(f"{item.key} {item.value}" for item in items)


# --- creating an account and signing in -----------------------------------------------------

def test_a_new_account_can_sign_in_and_is_known_by_its_name(store):
    accounts.create_account(store, "anna", "Anna Berg", PASSWORD)

    account = accounts.sign_in(store, "anna", PASSWORD)

    assert account.username == "anna"
    assert account.name == "Anna Berg"


def test_each_account_has_its_own_user_id(store):
    anna = accounts.create_account(store, "anna", "Anna", PASSWORD)
    ben = accounts.create_account(store, "ben", "Ben", PASSWORD)

    assert anna.user_id == "u-anna"
    assert ben.user_id == "u-ben"


def test_the_username_ignores_capitals_and_spaces_around_it(store):
    accounts.create_account(store, "  Anna ", "Anna", PASSWORD)

    assert accounts.sign_in(store, "ANNA", PASSWORD).username == "anna"


def test_the_password_itself_is_never_stored(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)

    assert PASSWORD not in everything_stored(store)


def test_two_accounts_with_the_same_password_are_stored_differently(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)
    accounts.create_account(store, "ben", "Ben", PASSWORD)

    anna, ben = (store.get(accounts.ACCOUNTS, name).value for name in ("anna", "ben"))
    assert anna["hash"] != ben["hash"]


def test_a_wrong_password_is_refused(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)

    with pytest.raises(AccountError) as refused:
        accounts.sign_in(store, "anna", "correct horse batter")

    assert str(refused.value) == "That username and password don't match. Try again."


def test_an_unknown_username_gets_the_same_message_as_a_wrong_password(store):
    with pytest.raises(AccountError) as refused:
        accounts.sign_in(store, "nobody", PASSWORD)

    assert str(refused.value) == "That username and password don't match. Try again."


# --- what is accepted when an account is created ---------------------------------------------

def test_a_username_that_is_taken_is_refused(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)

    with pytest.raises(AccountError) as refused:
        accounts.create_account(store, "Anna", "Another Anna", "a different password")

    assert str(refused.value) == "That username is taken. Choose another."
    # The first account is untouched.
    assert accounts.sign_in(store, "anna", PASSWORD).name == "Anna"


def test_a_password_shorter_than_eight_characters_is_refused(store):
    with pytest.raises(AccountError) as refused:
        accounts.create_account(store, "anna", "Anna", "1234567")

    assert str(refused.value) == "Use a password of at least 8 characters."


@pytest.mark.parametrize("username", ["", "ab", "anna berg", "anna/../x", "a" * 31, "ünna"])
def test_a_username_must_be_3_to_30_plain_characters(store, username):
    with pytest.raises(AccountError) as refused:
        accounts.create_account(store, username, "Anna", PASSWORD)

    assert str(refused.value) == ("Use a username of 3 to 30 characters: "
                                  "letters, digits, dot, dash or underscore.")


def test_a_name_is_needed(store):
    with pytest.raises(AccountError) as refused:
        accounts.create_account(store, "anna", "   ", PASSWORD)

    assert str(refused.value) == "Enter your name."


def test_a_name_is_kept_to_one_short_line(store):
    account = accounts.create_account(store, "anna", "Anna\nBerg " + "x" * 100, PASSWORD)

    assert account.name == ("Anna Berg " + "x" * 100)[:40]


# --- the wait after too many wrong tries -----------------------------------------------------

def wrong_tries(store, count: int, now: float) -> None:
    for _ in range(count):
        with pytest.raises(AccountError):
            accounts.sign_in(store, "anna", "a wrong password", now=now)


def test_after_five_wrong_tries_even_the_right_password_must_wait(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)
    wrong_tries(store, 5, now=1000.0)

    with pytest.raises(AccountError) as refused:
        accounts.sign_in(store, "anna", PASSWORD, now=1001.0)

    assert str(refused.value) == "Too many wrong tries. Wait a minute and try again."


def test_four_wrong_tries_do_not_lock_the_account(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)
    wrong_tries(store, 4, now=1000.0)

    assert accounts.sign_in(store, "anna", PASSWORD, now=1001.0).username == "anna"


def test_after_the_wait_the_right_password_works_again(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)
    wrong_tries(store, 5, now=1000.0)

    assert accounts.sign_in(store, "anna", PASSWORD, now=1061.0).username == "anna"


def test_signing_in_clears_the_count_of_wrong_tries(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)
    wrong_tries(store, 4, now=1000.0)
    accounts.sign_in(store, "anna", PASSWORD, now=1001.0)

    wrong_tries(store, 4, now=1002.0)           # four more, not a fifth

    assert accounts.sign_in(store, "anna", PASSWORD, now=1003.0).username == "anna"


def test_wrong_tries_on_one_account_do_not_lock_another(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)
    accounts.create_account(store, "ben", "Ben", PASSWORD)
    wrong_tries(store, 5, now=1000.0)

    assert accounts.sign_in(store, "ben", PASSWORD, now=1001.0).username == "ben"


# --- the invite code ---------------------------------------------------------------------------

def test_only_the_exact_invite_code_is_accepted(store):
    accounts.check_invite_code(store, "open sesame", "open sesame", now=1000.0)

    with pytest.raises(AccountError) as refused:
        accounts.check_invite_code(store, "Open sesame", "open sesame", now=1000.0)

    assert str(refused.value) == "That invite code isn't right."


def test_after_five_wrong_invite_codes_the_right_one_must_wait(store):
    for _ in range(5):
        with pytest.raises(AccountError):
            accounts.check_invite_code(store, "a guess", "open sesame", now=1000.0)

    with pytest.raises(AccountError) as refused:
        accounts.check_invite_code(store, "open sesame", "open sesame", now=1001.0)

    assert str(refused.value) == "Too many wrong tries. Wait a minute and try again."
    accounts.check_invite_code(store, "open sesame", "open sesame", now=1061.0)   # no error
