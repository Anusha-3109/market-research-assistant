"""Small checks at the edge of the app: is the user's message usable, and
how should a failure be explained to them?"""

from agent.config import MAX_QUESTION_CHARS


def check_question(text: str) -> str | None:
    """Return a message explaining what is wrong with a question, or None
    if it can be sent.

    A very long message is refused before it reaches the model: it would
    cost money to process, and pasting a wall of text is also a common way
    to try to smuggle instructions in.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return "Type a question first."
    if len(cleaned) > MAX_QUESTION_CHARS:
        return (f"That message is {len(cleaned):,} characters long. Please keep "
                f"it under {MAX_QUESTION_CHARS:,}: name the product and the country, "
                f"and add your idea in a sentence or two.")
    return None


def friendly_error(error: Exception) -> str:
    """Turn a technical failure into a sentence a user can act on.

    The original text is matched loosely, because the same problem arrives
    worded differently from different services.
    """
    text = str(error)
    lowered = text.lower()

    if "401" in text or "unauthorized" in lowered or "invalid api key" in lowered:
        return ("An API key was rejected. Check the keys in the .env file and "
                "restart the app.")
    if "402" in text or "insufficient" in lowered or "credit" in lowered:
        return ("The model provider reports that the account is out of credit. "
                "Top it up and try again.")
    if "429" in text or "rate limit" in lowered or "too many requests" in lowered:
        return ("The service is receiving too many requests right now. Wait a "
                "minute and try again.")
    if "timed out" in lowered or "timeout" in lowered:
        return "The request took too long and was stopped. Try again."
    if "connection" in lowered or "network" in lowered or "getaddrinfo" in lowered:
        return ("The app could not reach the internet. Check your connection "
                "and try again.")
    return f"Something went wrong: {text[:300]}"
