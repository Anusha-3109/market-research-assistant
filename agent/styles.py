"""Answer styles: how the assistant words what it says.

The user picks one in the app's settings. A style changes the wording only.
It never changes what is true: the facts, the numbers and the source links
are the same in every style, and the checks on a report run regardless.

Each style is a short instruction added to what the model is told. The
default, "Balanced", adds nothing, so the assistant behaves exactly as it
did before styles existed.

The list of styles and the default are settings, kept with the others in
agent/config.py.
"""

from agent.config import ANSWER_STYLE, STYLE_CHOICES

# What the model is told for each style in STYLE_CHOICES. The default style
# has no entry on purpose.
STYLE_INSTRUCTIONS = {
    "Formal": (
        "Write in a formal, professional register: complete sentences, "
        "precise terms, no contractions, no exclamation marks. Suitable for "
        "a document handed to a bank or a business partner."),
    "Friendly": (
        "Write in a warm, plain way, as to someone starting their first "
        "business. Explain any business term in everyday words the first "
        "time you use it. Be encouraging, but never make a finding sound "
        "better than the sources show."),
    "Concise": (
        "Give the shortest useful answer. Lead with the answer itself, use "
        "short bullet points, and leave out introductions, repetition and "
        "closing remarks."),
}

# The same sentence ends every style's instruction.
# The second sentence was added after a test run: asked to be friendly, the
# model kept the figures but left out the link to where they came from.
FACTS_STAY = ("This changes the wording only. The facts, the numbers and the "
              "source links stay exactly the same. Every fact still ends with "
              "its [source](link), as in any other style.")


def known_style(style: str | None) -> str:
    """The style to use: the one given if it exists, otherwise the default.
    A setting is never trusted to hold a valid name."""
    return style if style in STYLE_CHOICES else ANSWER_STYLE


def style_instruction(style: str | None) -> str:
    """The instruction for a style, or an empty string for the default."""
    instruction = STYLE_INSTRUCTIONS.get(known_style(style))
    return f"{instruction} {FACTS_STAY}" if instruction else ""


def style_for_prompt(style: str | None) -> str:
    """The section added to the chat agent's system prompt, or an empty
    string for the default style.

    It comes last, after the standing instructions and the saved profile,
    and says what it overrides and what it must leave alone. Each line
    below answers a question the model would otherwise have to guess:

    - The standing instructions end with their own "Style" section, which
      asks for concise answers in bullet points. Formal asks for complete
      sentences, so the prompt says which of the two to follow.
    - The user may have a remembered style from an earlier message. The
      setting chosen now is the newer and more explicit of the two.
    - A style is about wording. Asked to be concise, a model might turn a
      table into bullets or soften a refusal; neither is wording.
    """
    instruction = style_instruction(style)
    if not instruction:
        return ""
    return (
        "\n## How to write\n"
        f"The user chose the \"{known_style(style)}\" answer style in the app's "
        f"settings. {instruction}\n"
        "- This replaces the \"Style\" section above. Where the two differ, "
        "follow this one.\n"
        "- If a saved report style in the profile above contradicts this, "
        "this choice wins; keep following the saved one wherever it does not "
        "contradict.\n"
        "- A table stays a table. When a request must be declined, decline "
        "exactly as the rules above say; the style changes the tone of a "
        "refusal, never whether you refuse.\n"
        "- This applies to your own answers. A report made by the report tool "
        "is shown as it is; never rewrite it.\n"
    )
