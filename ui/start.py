"""The start screen: headline and example cards, shown while a conversation
is empty.

The cards float across the whole main area, around the headline (their
positions are set in ui/styles.py). Only on a phone-sized screen do they
fall back to the plain rows of three built here.
"""

import streamlit as st

from agent.config import APP_NAME

# (icon, title, example shown on the card, question sent to the agent)
EXAMPLES = [
    (":material/description:", "Write a report", "Healthy meal delivery in Germany",
     "Give me a market research report for healthy meal delivery in Germany."),
    (":material/trending_up:", "Check demand", "Is interest in meal kits rising in Germany?",
     "Is interest in meal kits rising in Germany?"),
    (":material/sell:", "Compare prices", "What does Prepmymeal charge?",
     "What does Prepmymeal charge for its meals in Germany?"),
    (":material/newspaper:", "Follow the news", "What changed in organic baby food in France?",
     "What has changed recently in the organic baby food market in France?"),
    (":material/groups:", "Find competitors", "Who sells vegan protein snacks in the UK?",
     "Who are the main companies selling vegan protein snacks in the United Kingdom?"),
    (":material/apartment:", "Research a company", "How big is HelloFresh?",
     "How big is HelloFresh? Give me its revenue and number of employees."),
    (":material/straighten:", "Size a market", "How big is the vegan snack market in the UK?",
     "How big is the vegan snack market in the United Kingdom?"),
    (":material/lightbulb:", "Test my idea", "A vegan bakery in the Netherlands",
     "I want to open a vegan bakery in the Netherlands. Give me a market research report."),
    (":material/person_pin_circle:", "Set your market", "I am based in Germany, in meal delivery",
     "I am based in Germany and I am planning a meal delivery business."),
]
CARDS_PER_ROW = 3

# Returned by render_start_screen when the wide card was clicked.
OPEN_GUIDE = "__open_guide__"


def render_start_screen() -> str | None:
    """Show the headline and the cards. Returns the question of the example
    card that was clicked, OPEN_GUIDE if the wide card was clicked, or None."""
    chosen = None

    with st.container(key="hero"):
        st.title("Research **any market**.", anchor=False)
        st.markdown("Verified competitors, first-hand prices, every fact linked to its source.")

    with st.container(key="cards"):
        for start in range(0, len(EXAMPLES), CARDS_PER_ROW):
            columns = st.columns(CARDS_PER_ROW)
            for offset, column in enumerate(columns):
                chosen = _card(column, start + offset) or chosen

    # The wide card above the question box. It opens the guide; it does not
    # send a question to the assistant.
    if st.button(f"Learn how **{APP_NAME}** works.", key="learn",
                 icon=":material/travel_explore:"):
        return OPEN_GUIDE

    return chosen


def _card(column, index: int) -> str | None:
    icon, title, example, question = EXAMPLES[index]
    with column:
        # Two paragraphs in the label: a bold title, then the example.
        if st.button(f"**{title}**\n\n{example}", key=f"card_{index}", icon=icon,
                     width="stretch", wrap=True):
            return question
    return None
