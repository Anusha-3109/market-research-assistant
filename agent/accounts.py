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
# A link for a forgotten password: the hash of its token, and who it is for.
RESETS = ("password_resets",)
# Per username: when links were asked for, and which one is the latest.
RESET_REQUESTS = ("password_reset_requests",)

USERNAME = re.compile(r"[a-z0-9._-]{3,30}")
NAME_MAX_CHARS = 40
PASSWORD_MIN_CHARS = 8
PASSWORD_MAX_CHARS = 200

# After this many wrong tries in a row, further tries must wait.
TRIES_ALLOWED = 5
WAIT_SECONDS = 60

# A plain check of the shape, not proof that the address exists. No spaces
# or line breaks can get through, which matters when it is put in an email.
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}")
EMAIL_MAX_CHARS = 254

# A link for a forgotten password works once, for this long.
RESET_LINK_SECONDS = 30 * 60
# At most this many links are given out per account per hour.
RESET_LINKS_PER_HOUR = 3

NO_MATCH = "That username and password don't match. Try again."
MUST_WAIT = "Too many wrong tries. Wait a minute and try again."
WRONG_CODE = "That invite code isn't right."
NOT_CURRENT = "That is not your current password."
BAD_EMAIL = "Enter a valid email address."
LINK_DEAD = "This link has expired or was already used. Ask for a new one."
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


def clean_email(email: str) -> str:
    """An email address in lower case, or "" if none was given. Raises
    AccountError if it does not look like an address."""
    email = email.strip().lower()
    if email and not (EMAIL.fullmatch(email) and len(email) <= EMAIL_MAX_CHARS):
        raise AccountError(BAD_EMAIL)
    return email


def _check_new_password(password: str) -> None:
    if len(password) < PASSWORD_MIN_CHARS:
        raise AccountError(f"Use a password of at least {PASSWORD_MIN_CHARS} characters.")
    if len(password) > PASSWORD_MAX_CHARS:
        raise AccountError(f"Use a password of at most {PASSWORD_MAX_CHARS} characters.")


def _password_fields(password: str) -> dict:
    """What is stored for a password: a fresh salt and the hash."""
    salt = secrets.token_bytes(16)
    return {"salt": salt.hex(), "hash": _hash(password, salt)}


def create_account(store: BaseStore, username: str, name: str, password: str,
                   email: str = "") -> Account:
    """Create an account and return it. Raises AccountError, with a message
    for the person, if something is not acceptable.

    The email address is where a link for a forgotten password is sent. An
    account without one cannot use that.
    """
    username = clean_username(username)
    name = " ".join(name.split())[:NAME_MAX_CHARS]
    if not USERNAME.fullmatch(username):
        raise AccountError(BAD_USERNAME)
    if not name:
        raise AccountError("Enter your name.")
    email = clean_email(email)
    _check_new_password(password)

    record = {"name": name, "email": email, **_password_fields(password),
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


# --- changing the password or the email address ---------------------------------------------

def _confirm_password(store: BaseStore, username: str, password: str, now: float | None) -> None:
    """Raise AccountError unless this is the account's current password.
    Wrong ones are counted like wrong sign-ins."""
    try:
        sign_in(store, username, password, now=now)
    except AccountError as refused:
        raise AccountError(NOT_CURRENT if str(refused) == NO_MATCH else str(refused)) from None


def _update(store: BaseStore, username: str, changes: dict) -> None:
    username = clean_username(username)
    with _lock:
        store.put(ACCOUNTS, username, {**store.get(ACCOUNTS, username).value, **changes})


def change_password(store: BaseStore, username: str, current: str, new: str,
                    now: float | None = None) -> None:
    """Replace the password of an account. The current one must be given:
    someone who finds a browser left open cannot lock its owner out."""
    _confirm_password(store, username, current, now)
    _check_new_password(new)
    if same(new, current):
        raise AccountError("Choose a password that differs from the current one.")
    _update(store, username, _password_fields(new))


def email_of(store: BaseStore, username: str) -> str:
    """The email address of an account, or "" if it has none."""
    item = store.get(ACCOUNTS, clean_username(username))
    return item.value.get("email", "") if item else ""


def set_email(store: BaseStore, username: str, current_password: str, email: str,
              now: float | None = None) -> None:
    """Change where a link for a forgotten password is sent. The current
    password must be given: otherwise someone at an open browser could
    point the links at their own address and take the account."""
    _confirm_password(store, username, current_password, now)
    email = clean_email(email)
    if not email:
        raise AccountError(BAD_EMAIL)
    _update(store, username, {"email": email})


# --- a forgotten password ------------------------------------------------------------------
#
# The person asks for a link, which is sent to the email address of the
# account. The link holds a long random token. Only a hash of the token is
# stored, so someone who reads the store cannot use it. The token is random
# and long, so a fast hash is enough here; the slow one is for passwords,
# which people choose and which can be guessed.

@dataclass(frozen=True)
class Reset:
    """A link that was just made: who it is for, where to send it, and the
    token to put in it."""

    account: Account
    email: str
    token: str


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_reset(store: BaseStore, username: str, now: float | None = None) -> Reset | None:
    """Make a link for a forgotten password. Returns None if there is no
    such account, it has no email address, or too many links were asked
    for; the caller says the same thing to the person in every case."""
    now = time.time() if now is None else now
    username = clean_username(username)
    item = store.get(ACCOUNTS, username) if USERNAME.fullmatch(username) else None
    email = item.value.get("email", "") if item else ""
    if not email:
        return None

    with _lock:
        earlier = store.get(RESET_REQUESTS, username)
        asked = [at for at in (earlier.value["asked"] if earlier else []) if now - at < 3600]
        if len(asked) >= RESET_LINKS_PER_HOUR:
            return None
        if earlier and earlier.value.get("latest"):
            store.delete(RESETS, earlier.value["latest"])      # the earlier link is cancelled
        token = secrets.token_urlsafe(32)
        store.put(RESETS, _token_key(token),
                  {"username": username, "expires": now + RESET_LINK_SECONDS})
        store.put(RESET_REQUESTS, username, {"asked": asked + [now], "latest": _token_key(token)})
    return Reset(Account(username, item.value["name"]), email, token)


def account_for_reset(store: BaseStore, token: str, now: float | None = None) -> Account | None:
    """The account a link is for, or None if the link is unknown, used or
    too old."""
    now = time.time() if now is None else now
    link = store.get(RESETS, _token_key(token))
    if not link or now >= link.value["expires"]:
        return None
    item = store.get(ACCOUNTS, link.value["username"])
    return Account(link.value["username"], item.value["name"]) if item else None


def finish_reset(store: BaseStore, token: str, new_password: str,
                 now: float | None = None) -> Account:
    """Set a new password with a link. The link then stops working."""
    account = account_for_reset(store, token, now)
    if account is None:
        raise AccountError(LINK_DEAD)
    _check_new_password(new_password)      # a refused password leaves the link usable
    _update(store, account.username, _password_fields(new_password))
    store.delete(RESETS, _token_key(token))
    _forget_wrong_tries(store, account.username[:60])
    return account
