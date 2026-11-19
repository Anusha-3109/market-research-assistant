"""The language the models write in.

The app's own words follow the language switch (ui/words). This file is
about what the language models write: with German chosen, the chat agent,
the assistant and the report workflow are told to write in German.
"""

from agent.config import LANGUAGE, LANGUAGE_CHOICES

# Added to the instructions of the chat agent and of the assistant.
ANSWER_IN = {
    "de": ('\n\n## Language\nWrite your answer in German. Address the user formally, with "Sie". '
           "Keep company names, product names, figures and links exactly as they are. "
           "Arguments and country names you pass to tools stay in English."),
}

# Added to every request of the report workflow.
REPORT_IN = {
    "de": ("\n\nWrite every description, statement and analysis point in German. Keep company "
           "names, product names, numbers, currencies, dates and web addresses exactly as they "
           "are. A field that asks for a value in English, or for one word from a fixed list, "
           "stays as it asks."),
}


def known_language(language: str | None) -> str:
    """The language if the app has it, otherwise English."""
    return language if language in LANGUAGE_CHOICES else LANGUAGE


def answer_instruction(language: str | None) -> str:
    """What is added to a chat prompt; nothing for English."""
    return ANSWER_IN.get(known_language(language), "")


def report_instruction(language: str | None) -> str:
    """What is added to each request of the report workflow."""
    return REPORT_IN.get(known_language(language), "")
