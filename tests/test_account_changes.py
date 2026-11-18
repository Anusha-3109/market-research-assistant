"""Tests for what an account holder can change: the password, the email
address, and a forgotten password by way of a link.

The store is held in RAM and the people are made up.
"""

import pytest
from langgraph.store.memory import InMemoryStore

from agent import accounts
from agent.accounts import AccountError
from tests.test_accounts import PASSWORD, everything_stored, wrong_tries

NEW_PASSWORD = "a brand new password"


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def anna(store):
    """A store with one account, anna, that has an email address."""
    accounts.create_account(store, "anna", "Anna", PASSWORD, email="anna@example.com")
    return store


# --- changing your password ----------------------------------------------------------------------

def test_after_a_change_only_the_new_password_signs_in(anna):
    accounts.change_password(anna, "anna", PASSWORD, NEW_PASSWORD)

    assert accounts.sign_in(anna, "anna", NEW_PASSWORD).username == "anna"
    with pytest.raises(AccountError):
        accounts.sign_in(anna, "anna", PASSWORD)


def test_a_change_needs_the_current_password(anna):
    with pytest.raises(AccountError) as refused:
        accounts.change_password(anna, "anna", "not the current one", NEW_PASSWORD)

    assert str(refused.value) == "That is not your current password."
    assert accounts.sign_in(anna, "anna", PASSWORD).username == "anna"      # unchanged


def test_wrong_current_passwords_are_counted_like_wrong_sign_ins(anna):
    for _ in range(5):
        with pytest.raises(AccountError):
            accounts.change_password(anna, "anna", "a guess", NEW_PASSWORD, now=1000.0)

    with pytest.raises(AccountError) as refused:
        accounts.change_password(anna, "anna", PASSWORD, NEW_PASSWORD, now=1001.0)

    assert str(refused.value) == "Too many wrong tries. Wait a minute and try again."


def test_the_new_password_must_be_long_enough_and_different(anna):
    with pytest.raises(AccountError) as too_short:
        accounts.change_password(anna, "anna", PASSWORD, "1234567")
    with pytest.raises(AccountError) as the_same:
        accounts.change_password(anna, "anna", PASSWORD, PASSWORD)

    assert str(too_short.value) == "Use a password of at least 8 characters."
    assert str(the_same.value) == "Choose a password that differs from the current one."
    assert accounts.sign_in(anna, "anna", PASSWORD).username == "anna"


def test_a_change_keeps_the_name_and_the_email_address(anna):
    accounts.change_password(anna, "anna", PASSWORD, NEW_PASSWORD)

    assert accounts.sign_in(anna, "anna", NEW_PASSWORD).name == "Anna"
    assert accounts.email_of(anna, "anna") == "anna@example.com"


# --- the email address ---------------------------------------------------------------------------

def test_an_account_keeps_its_email_address_in_lower_case(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD, email="  Anna@Example.com ")

    assert accounts.email_of(store, "anna") == "anna@example.com"


def test_an_account_made_without_an_email_has_none(store):
    accounts.create_account(store, "anna", "Anna", PASSWORD)

    assert accounts.email_of(store, "anna") == ""


@pytest.mark.parametrize("email", ["anna", "anna@", "@example.com", "anna@example",
                                   "anna berg@example.com", "anna@example.com\nBcc: x@y.zz",
                                   "a" * 250 + "@example.com"])
def test_something_that_is_not_an_email_address_is_refused(store, email):
    with pytest.raises(AccountError) as refused:
        accounts.create_account(store, "anna", "Anna", PASSWORD, email=email)

    assert str(refused.value) == "Enter a valid email address."


def test_the_email_address_is_changed_only_with_the_current_password(anna):
    with pytest.raises(AccountError) as refused:
        accounts.set_email(anna, "anna", "not the password", "thief@example.com")
    assert str(refused.value) == "That is not your current password."
    assert accounts.email_of(anna, "anna") == "anna@example.com"

    accounts.set_email(anna, "anna", PASSWORD, "Anna.Berg@example.com")

    assert accounts.email_of(anna, "anna") == "anna.berg@example.com"
    assert accounts.sign_in(anna, "anna", PASSWORD).username == "anna"      # the password is kept


def test_a_new_email_address_must_be_valid(anna):
    with pytest.raises(AccountError) as refused:
        accounts.set_email(anna, "anna", PASSWORD, "not an address")

    assert str(refused.value) == "Enter a valid email address."
    assert accounts.email_of(anna, "anna") == "anna@example.com"


# --- a forgotten password ---------------------------------------------------------------------------

def test_a_reset_is_started_for_an_account_with_an_email_address(anna):
    reset = accounts.start_reset(anna, " Anna ", now=1000.0)

    assert reset.account.username == "anna"
    assert reset.email == "anna@example.com"
    assert len(reset.token) >= 40                    # long enough that it cannot be guessed


def test_no_reset_is_started_for_an_unknown_account_or_one_without_an_email(store):
    accounts.create_account(store, "ben", "Ben", PASSWORD)

    assert accounts.start_reset(store, "nobody", now=1000.0) is None
    assert accounts.start_reset(store, "ben", now=1000.0) is None


def test_the_link_sets_a_new_password(anna):
    token = accounts.start_reset(anna, "anna", now=1000.0).token

    assert accounts.account_for_reset(anna, token, now=1060.0).username == "anna"
    accounts.finish_reset(anna, token, NEW_PASSWORD, now=1060.0)

    assert accounts.sign_in(anna, "anna", NEW_PASSWORD).username == "anna"
    with pytest.raises(AccountError):
        accounts.sign_in(anna, "anna", PASSWORD)


def test_the_link_works_only_once(anna):
    token = accounts.start_reset(anna, "anna", now=1000.0).token
    accounts.finish_reset(anna, token, NEW_PASSWORD, now=1060.0)

    with pytest.raises(AccountError) as refused:
        accounts.finish_reset(anna, token, "yet another password", now=1070.0)

    assert str(refused.value) == "This link has expired or was already used. Ask for a new one."
    assert accounts.account_for_reset(anna, token, now=1070.0) is None
    assert accounts.sign_in(anna, "anna", NEW_PASSWORD).username == "anna"


def test_the_link_stops_working_after_30_minutes(anna):
    token = accounts.start_reset(anna, "anna", now=1000.0).token

    assert accounts.account_for_reset(anna, token, now=1000.0 + 29 * 60) is not None
    assert accounts.account_for_reset(anna, token, now=1000.0 + 31 * 60) is None
    with pytest.raises(AccountError):
        accounts.finish_reset(anna, token, NEW_PASSWORD, now=1000.0 + 31 * 60)
    assert accounts.sign_in(anna, "anna", PASSWORD).username == "anna"       # unchanged


def test_a_made_up_link_is_refused(anna):
    accounts.start_reset(anna, "anna", now=1000.0)

    assert accounts.account_for_reset(anna, "a-made-up-token", now=1001.0) is None
    with pytest.raises(AccountError):
        accounts.finish_reset(anna, "a-made-up-token", NEW_PASSWORD, now=1001.0)


def test_the_link_itself_is_never_stored(anna):
    token = accounts.start_reset(anna, "anna", now=1000.0).token

    assert token not in everything_stored(anna)


def test_asking_again_cancels_the_earlier_link(anna):
    first = accounts.start_reset(anna, "anna", now=1000.0).token
    second = accounts.start_reset(anna, "anna", now=1100.0).token

    assert accounts.account_for_reset(anna, first, now=1101.0) is None
    assert accounts.account_for_reset(anna, second, now=1101.0).username == "anna"


def test_at_most_three_links_are_given_out_per_account_per_hour(anna):
    for minute in (0, 1, 2):
        assert accounts.start_reset(anna, "anna", now=1000.0 + minute * 60) is not None

    assert accounts.start_reset(anna, "anna", now=1000.0 + 3 * 60) is None
    assert accounts.start_reset(anna, "anna", now=1000.0 + 62 * 60) is not None     # an hour later


def test_a_refused_fourth_request_leaves_the_third_link_working(anna):
    for minute in (0, 1):
        accounts.start_reset(anna, "anna", now=1000.0 + minute * 60)
    third = accounts.start_reset(anna, "anna", now=1000.0 + 2 * 60).token

    accounts.start_reset(anna, "anna", now=1000.0 + 3 * 60)

    assert accounts.account_for_reset(anna, third, now=1000.0 + 4 * 60) is not None


def test_the_new_password_of_a_reset_must_be_long_enough(anna):
    token = accounts.start_reset(anna, "anna", now=1000.0).token

    with pytest.raises(AccountError) as refused:
        accounts.finish_reset(anna, token, "1234567", now=1001.0)

    assert str(refused.value) == "Use a password of at least 8 characters."
    # The link is still good for a second try.
    assert accounts.account_for_reset(anna, token, now=1002.0) is not None


def test_a_reset_ends_the_wait_after_too_many_wrong_tries(anna):
    wrong_tries(anna, 5, now=1000.0)
    token = accounts.start_reset(anna, "anna", now=1001.0).token

    accounts.finish_reset(anna, token, NEW_PASSWORD, now=1002.0)

    assert accounts.sign_in(anna, "anna", NEW_PASSWORD, now=1003.0).username == "anna"
