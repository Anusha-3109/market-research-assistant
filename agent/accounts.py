"""User accounts: creating one and signing in.

Accounts are kept in the same store as the agent's long-term memory, so
they are saved and copied with it.

A password is never stored. What is stored is a "hash": the result of a
slow one-way calculation on the password and a random value (the "salt").
Signing in repeats the calculation and compares the results. Someone who
reads the store cannot turn a hash back into the password, and two people
with the same password have different hashes.

Nothing here imports Streamlit, so it can be tested without a browser.
"""

import hashlib
import hmac
import re
import secrets
import threading
import time
from dataclasses import dataclass

from langgraph.store.base import BaseStore

# Where accounts and the counts of wrong tries are kept in the store.
ACCOUNTS = ("accounts",)
WRONG_TRIES = ("wrong_tries",)

USERNAME = re.compile(r"[a-z0-9._-]{3,30}")
NAME_MAX_CHARS = 40
PASSWORD_MIN_CHARS = 8
PASSWORD_MAX_CHARS = 200

# After this many wrong tries in a row, further tries must wait.
TRIES_ALLOWED = 5
WAIT_SECONDS = 60

NO_MATCH = "That username and password don't match. Try again."
MUST_WAIT = "Too many wrong tries. Wait a minute and try again."
WRONG_CODE = "That invite code isn't right."
BAD_USERNAME = ("Use a username of 3 to 30 characters: "
                "letters, digits, dot, dash or underscore.")

# The key under which wrong invite codes are counted. It cannot be a
# username: a username has no colon.
INVITE_TRIES = "invite:code"

_lock = threading.Lock()


class AccountError(ValueError):
    """An account could not be created, or a sign-in was refused. The
    message is written for the person at the screen."""


@dataclass(frozen=True)
class Account:
    username: str
    name: str

    @property
    def user_id(self) -> str:
        """The id under which this person's memory and conversations are
        kept. The prefix keeps it apart from the id used when the app runs
        without accounts."""
        return f"u-{self.username}"


# --- passwords ------------------------------------------------------------------------------

def _hash(password: str, salt: bytes) -> str:
    """The slow one-way calculation. scrypt is made for passwords: it is
    costly on purpose, so guessing many passwords takes a long time."""
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32).hex()


def same(typed: str, expected: str) -> bool:
    """Compare in a way that takes the same time whether the first or the
    last character is wrong, so the time taken reveals nothing."""
    return hmac.compare_digest(typed.encode(), expected.encode())


# --- the wait after too many wrong tries -------------------------------------------------
#
# Wrong tries are counted per username (and once for the invite code), in
# the store, so opening a new browser window does not reset the count.

def _check_may_try(store: BaseStore, key: str, now: float) -> None:
    item = store.get(WRONG_TRIES, key)
    if item and now < item.value.get("wait_until", 0):
        raise AccountError(MUST_WAIT)


def _note_wrong_try(store: BaseStore, key: str, now: float) -> None:
    item = store.get(WRONG_TRIES, key)
    count = (item.value["count"] if item else 0) + 1
    wait_until = now + WAIT_SECONDS if count >= TRIES_ALLOWED else 0
    store.put(WRONG_TRIES, key, {"count": count, "wait_until": wait_until})


def _forget_wrong_tries(store: BaseStore, key: str) -> None:
    if store.get(WRONG_TRIES, key):
        store.delete(WRONG_TRIES, key)


# --- creating an account and signing in ---------------------------------------------------

def clean_username(username: str) -> str:
    return username.strip().lower()


def create_account(store: BaseStore, username: str, name: str, password: str) -> Account:
    """Create an account and return it. Raises AccountError, with a message
    for the person, if something is not acceptable."""
    username = clean_username(username)
    name = " ".join(name.split())[:NAME_MAX_CHARS]
    if not USERNAME.fullmatch(username):
        raise AccountError(BAD_USERNAME)
    if not name:
        raise AccountError("Enter your name.")
    if len(password) < PASSWORD_MIN_CHARS:
        raise AccountError(f"Use a password of at least {PASSWORD_MIN_CHARS} characters.")
    if len(password) > PASSWORD_MAX_CHARS:
        raise AccountError(f"Use a password of at most {PASSWORD_MAX_CHARS} characters.")

    salt = secrets.token_bytes(16)
    record = {"name": name, "salt": salt.hex(), "hash": _hash(password, salt),
              "created": time.time()}
    # The lock stops two people from taking the same username at the same
    # moment.
    with _lock:
        if store.get(ACCOUNTS, username):
            raise AccountError("That username is taken. Choose another.")
        store.put(ACCOUNTS, username, record)
    return Account(username, name)


def sign_in(store: BaseStore, username: str, password: str, now: float | None = None) -> Account:
    """Return the account if the username and password belong together.
    Otherwise raise AccountError.

    An unknown username and a wrong password give the same message and
    take the same time, so the answer does not reveal which usernames
    exist.
    """
    now = time.time() if now is None else now
    username = clean_username(username)
    key = username[:60]
    _check_may_try(store, key, now)

    item = store.get(ACCOUNTS, username) if USERNAME.fullmatch(username) else None
    record = item.value if item else {"salt": "00" * 16, "hash": ""}
    matches = same(_hash(password[:PASSWORD_MAX_CHARS], bytes.fromhex(record["salt"])),
                   record["hash"])
    if not (item and matches):
        _note_wrong_try(store, key, now)
        raise AccountError(NO_MATCH)

    _forget_wrong_tries(store, key)
    return Account(username, record["name"])


def check_invite_code(store: BaseStore, typed: str, expected: str,
                      now: float | None = None) -> None:
    """Raise AccountError unless the invite code is the right one. Wrong
    codes are counted like wrong passwords."""
    now = time.time() if now is None else now
    _check_may_try(store, INVITE_TRIES, now)
    if not same(typed, expected):
        _note_wrong_try(store, INVITE_TRIES, now)
        raise AccountError(WRONG_CODE)
    _forget_wrong_tries(store, INVITE_TRIES)
