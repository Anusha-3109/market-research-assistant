"""The "How it works" guide.

Clicking the wide card on the start screen shows this explanation in the
chat area, as if the user had asked how the app works. It is fixed text:
it appears at once, costs nothing, and is not saved as a conversation.

Two follow-up chips add further fixed answers below. A third chip runs an
example report.
"""

from html import escape

import streamlit as st

from agent.config import APP_NAME

EXAMPLE_REPORT = "Give me a market research report for healthy meal delivery in Germany."

# (title, one line, small tags, number of section dots)
STEPS = [
    ("Ask", "Name a product and a country.", [], 0),
    ("Find competitors", "Search, then check each company.", ["search", "verify"], 0),
    ("You review", "Approve, remove or add companies.", [], 0),
    ("Collect facts", "Four lookups run at the same time.",
     ["prices", "market", "news", "trend"], 0),
    ("Report", "Six sections, every fact linked.", [], 6),
]

# Each topic: the question shown in the dark bubble, whether the row of step
# cards is shown above it, and the answer in markdown.
TOPICS = {
    "how": {
        "question": f"How does {APP_NAME} work?",
        "steps": True,
        "answer": f"""
{APP_NAME} works as a fixed five-step process. **{APP_NAME}** is the app; the
search results, news and company data come from public web sources.

1. **You ask.**  
   Name a product and one country, for example "healthy meal delivery in
   Germany". If the country is missing, it asks.
2. **It finds the real competitors.**  
   It searches the web, then checks each company: does it sell this product,
   in this country? Companies that fail are dropped, and you are told why.
3. **You review the list.**  
   Before the detailed research, you see the competitors it found. Remove
   any that do not belong, add ones it missed, or cancel.
4. **It collects the facts.**  
   Prices are read from each competitor's own website. Market figures are
   labelled with the area and year they cover. Recent news and
   search-interest trends are added.
5. **You get a report.**  
   Market overview, competitors, pricing, trends, SWOT analysis and
   references. Download it, or ask follow-up questions.

It will not give investment advice, and it never invents a number: what
cannot be found is reported as "not found".

A report takes about a minute. It remembers your country, industry and idea
for next time; say "forget my preferences" to clear them.
""",
        "note": "Figures come from public sources and are not verified "
                "statistics. Check the linked sources before making decisions.",
    },
    "prices": {
        "question": "Where do the prices come from?",
        "steps": False,
        "answer": """
Only from each competitor's own website.

- For every competitor, the app looks for that company's own pricing or
  product page and opens it.
- It lists the prices shown there, and keeps a price only if that exact
  number is on the page it opened.
- The source link next to a price is the page it was read from, so you can
  open it and check.
- Every price row shows the date it was found.

If a company's page cannot be read, or shows no prices, the report says
"not found". It does not fall back to a price from a blog, a review or an
old news article, because those are often out of date.
""",
        "note": "Some shops load their prices with scripts that the app "
                "cannot read. Those show as \"not found\" even though the "
                "shop does list prices.",
    },
    "competitors": {
        "question": "Why check the competitors?",
        "steps": False,
        "answer": """
Because a web search returns many companies that are not real competitors.

Searching for "meal delivery competitors in Germany" also brings up
companies that only operate in other countries, and companies in
neighbouring businesses such as grocery delivery. An early version of this
app listed those as competitors.

So each company the search finds is checked with two questions:

1. Is this product its main offer?
2. Does it sell to customers in this country?

A company must pass both, with a page that supports the answer. The rest are
dropped, and you see the reason for each. The ones that pass are ranked by
how often the search results mention them.

Then you review the list yourself, because you know your market better than
a search engine does.
""",
        "note": "The check relies on what search results say about a "
                "company. A product name can occasionally be mistaken for "
                "a company, which is one reason the list is shown to you.",
    },
}
FOLLOW_UPS = ["prices", "competitors"]


def steps_html() -> str:
    """The row of numbered step cards, as HTML. It is static, so plain HTML
    is used; the classes are styled in ui/styles.py."""
    cards = []
    for number, (title, line, tags, dots) in enumerate(STEPS, start=1):
        extras = "".join(f'<span class="gw-tag">{escape(tag)}</span>' for tag in tags)
        extras += "".join(f'<span class="gw-dot">{dot}</span>' for dot in range(1, dots + 1))
        cards.append(
            f'<div class="gw-step"><div class="gw-num">{number}</div>'
            f'<div class="gw-step-title">{escape(title)}</div>'
            f'<div class="gw-step-line">{escape(line)}</div>'
            f'<div>{extras}</div></div>'
        )
    return f'<div class="gw-steps">{"".join(cards)}</div>'


def render_topic(name: str) -> None:
    """One question bubble and its answer panel."""
    topic = TOPICS[name]
    st.html(f'<div class="gw-question"><span>{escape(topic["question"])}</span></div>')
    with st.container(key=f"guide_panel_{name}"):
        if topic["steps"]:
            st.html(steps_html())
        st.markdown(topic["answer"])
        st.caption("GOOD TO KNOW")
        st.caption(topic["note"])


# Streamlit keeps a chat page scrolled to the bottom, and does so again
# whenever the page changes size. The guide should be read from its top, so
# after a new answer is added this script holds the page at that answer's
# question bubble until the reader scrolls or clicks for themselves.
SCROLL_TO_NEWEST = """
<script>
(() => {
    const area = document.querySelector('[data-testid="stAppScrollToBottomContainer"]');
    if (!area) return;

    // The reader taking over ends the hold.
    let readerActed = false;
    for (const event of ['wheel', 'touchstart', 'keydown', 'mousedown']) {
        window.addEventListener(event, () => { readerActed = true; },
                                {once: true, passive: true});
    }

    const hold = () => {
        if (readerActed) return;
        const bubbles = document.querySelectorAll('.gw-question');
        if (!bubbles.length) return;
        const newest = bubbles[bubbles.length - 1];
        const offset = newest.getBoundingClientRect().top - area.getBoundingClientRect().top;
        const wanted = Math.max(0, area.scrollTop + offset - 70);
        if (Math.abs(area.scrollTop - wanted) > 4) area.scrollTop = wanted;
    };

    // Put it right whenever Streamlit moves the page. Once the reader has
    // acted, hold() does nothing, so the listener is harmless afterwards.
    area.addEventListener('scroll', hold);
    [100, 400, 900].forEach(delay => setTimeout(hold, delay));
})();
</script>
"""


def render_guide(guide: dict) -> str | None:
    """Show the guide.

    `guide` is the entry kept in the browser session: "topics" is the list
    of answers to show, in order, and "scroll" is True when a new answer
    was just added. Clicking a follow-up chip adds a topic.

    Returns a question to send to the assistant if the user clicked the
    example chip, "back" if they asked to return to the start screen,
    otherwise None.
    """
    shown = guide["topics"]
    for name in shown:
        render_topic(name)

    result = None
    with st.container(horizontal=True, key="guide_chips"):
        for name in FOLLOW_UPS:
            if name not in shown and st.button(
                    TOPICS[name]["question"], key=f"chip_{name}",
                    icon=":material/arrow_outward:", icon_position="right"):
                shown.append(name)
                guide["scroll"] = True
                st.rerun()
        if st.button("Try it: healthy meal delivery in Germany", key="chip_try",
                     icon=":material/arrow_outward:", icon_position="right"):
            result = EXAMPLE_REPORT
        if st.button("Back to start", key="chip_back", type="tertiary"):
            result = "back"

    if guide.pop("scroll", False):
        st.html(SCROLL_TO_NEWEST, unsafe_allow_javascript=True)
    return result
