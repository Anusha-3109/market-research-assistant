"""The app's look: a soft sky background with frosted-glass panels.

Streamlit's theme settings cannot produce a gradient or transparency, so
this is done with CSS. Where possible the rules target elements by the key
given to them in Python (Streamlit turns key="hero" into the CSS class
.st-key-hero). A few page-level parts (the page background, the top bar,
the bottom bar, chat bubbles) have no key and are targeted by Streamlit's
own test ids; those selectors may need updating after a Streamlit upgrade.
"""

import streamlit as st

SKY = (
    "radial-gradient(ellipse 60% 34% at 12% 100%, #f4b9b4 0, rgba(244,185,180,0) 70%),"
    "radial-gradient(ellipse 55% 30% at 86% 94%, #f7cfc0 0, rgba(247,207,192,0) 70%),"
    "radial-gradient(ellipse 50% 40% at 80% 10%, #fbeedd 0, rgba(251,238,221,0) 72%),"
    "linear-gradient(168deg, #b9dcec 0%, #d5e8ea 34%, #f6e6d8 62%, #f3cdc6 100%)"
)
GLASS = "rgba(255, 255, 255, 0.55)"
GLASS_STRONG = "rgba(255, 255, 255, 0.78)"
GLASS_EDGE = "rgba(255, 255, 255, 0.9)"

CSS = f"""
<style>
/* The page: a fixed sky that does not scroll with the content. */
.stApp {{
    background: {SKY};
    background-attachment: fixed;
}}
[data-testid="stHeader"] {{ background: transparent; }}
/* The bar holding the question box fades in, so text scrolling behind it
   does not show through the box. */
[data-testid="stBottom"] {{
    background: linear-gradient(to bottom, rgba(244, 212, 204, 0) 0,
                                rgba(244, 212, 204, 0.97) 22%);
}}
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {{ background: transparent; }}

/* The start screen headline. */
.st-key-hero {{ text-align: center; padding: 1.5rem 0 0.5rem; }}
.st-key-hero h1 {{
    font-size: clamp(2.4rem, 6vw, 4.2rem);
    font-weight: 400;
    letter-spacing: -0.03em;
    line-height: 1.05;
    padding: 0;
}}
.st-key-hero h1 strong {{ font-weight: 650; }}
.st-key-hero p {{ color: #55544f; font-size: 1.05rem; }}
.st-key-hero h1, .st-key-hero p, .st-key-hero [data-testid="stMarkdownContainer"] {{
    text-align: center !important;
    width: 100%;
}}
.st-key-hero [data-testid="stHeadingWithActionElements"] {{ justify-content: center; }}

/* The example cards: frosted glass, slightly staggered so they do not
   read as a strict grid. */
[class*="st-key-card_"] button {{
    background: {GLASS};
    border: 1px solid {GLASS_EDGE};
    border-radius: 14px;
    padding: 0.8rem 1rem;
    min-height: 5.6rem;
    text-align: left;
    justify-content: flex-start;
    align-items: flex-start;
    backdrop-filter: blur(6px);
    transition: background 120ms ease, transform 120ms ease;
}}
[class*="st-key-card_"] button:hover {{
    background: {GLASS_STRONG};
    border-color: #ffffff;
    transform: translateY(-2px);
}}
/* Streamlit keeps a button label on one line and cuts it with "...". The
   cards need two lines (title, then example), so that is undone here. */
[class*="st-key-card_"] button [data-testid="stMarkdownContainer"] {{
    display: block !important;
    text-align: left;
    white-space: normal !important;
    overflow: visible !important;
}}
[class*="st-key-card_"] button p {{
    font-size: 0.86rem; color: #55544f; line-height: 1.35;
    display: block !important; margin: 0 0 0.15rem;
    white-space: normal !important;
}}
[class*="st-key-card_"] button > div {{
    align-items: flex-start;
    justify-content: flex-start;
    width: 100%;
}}
[class*="st-key-card_"] button p strong {{ color: #1c1c1a; font-weight: 600; font-size: 0.92rem; }}
[class*="st-key-card_"] button {{ position: relative; }}
[class*="st-key-card_"] button::after {{
    content: "\\2197";              /* a small arrow, top right */
    position: absolute; right: 0.7rem; top: 0.45rem;
    color: #8a8880; font-size: 0.8rem;
}}

/* Floating layout. The cards are lifted out of their rows and placed at
   their own spots across the WHOLE main area, around the headline, and
   drift gently.

   Everything is measured against the main area (the page minus the
   sidebar), not the browser window:
   - the main area is declared a "container", so the rules below switch on
     by ITS width. Opening the sidebar, a small laptop screen or Windows
     display scaling all just make the main area narrower;
   - positions and card widths are percentages of the main area, and the
     headline size uses cqw (1% of the main area's width), so the layout
     shrinks and grows as one piece.
   Only on a phone-sized main area, or a very short window, do the cards
   stay in plain rows of three. */
[data-testid="stAppScrollToBottomContainer"] {{
    container-type: inline-size;
    container-name: main;
}}
@keyframes card-drift {{
    0%, 100% {{ transform: translateY(0); }}
    50%      {{ transform: translateY(-8px); }}
}}
@media (min-height: 620px) {{
@container main (min-width: 700px) {{
    .st-key-hero {{ margin-top: 27vh; }}
    .st-key-hero h1 {{ font-size: clamp(1.9rem, 5.4cqw, 4.4rem); }}
    .st-key-hero p {{ font-size: clamp(0.8rem, 1.5cqw, 1.05rem); }}

    [class*="st-key-card_"] {{
        position: absolute;
        width: clamp(8.6rem, 17.5cqw, 15rem);
        z-index: 2;
        animation: card-drift 7s ease-in-out infinite;
    }}
    [class*="st-key-card_"] button {{
        padding: clamp(0.45rem, 0.9cqw, 0.8rem) clamp(0.55rem, 1.1cqw, 1rem);
        padding-right: 1.5rem;      /* room for the arrow */
        min-height: 0;
    }}
    [class*="st-key-card_"] button p {{ font-size: clamp(0.7rem, 1.15cqw, 0.86rem); }}
    [class*="st-key-card_"] button p strong {{ font-size: clamp(0.74rem, 1.25cqw, 0.92rem); }}

    /* Three across the top, two down each side, two along the bottom. */
    .st-key-card_0 {{ left: 16%;   top: 15%; animation-delay: -1s; }}
    .st-key-card_1 {{ left: 41.2%; top: 7%;  animation-delay: -3s; }}
    .st-key-card_2 {{ right: 15%;  top: 14%; animation-delay: -4.5s; }}
    .st-key-card_3 {{ left: 1.8%;  top: 30%; animation-delay: -2s; }}
    .st-key-card_4 {{ right: 1.8%; top: 33%; animation-delay: -5.5s; }}
    .st-key-card_5 {{ left: 2.4%;  top: 55%; animation-delay: -0.5s; }}
    .st-key-card_6 {{ right: 2.2%; top: 57%; animation-delay: -3.5s; }}
    .st-key-card_7 {{ left: 18%;   top: 69%; animation-delay: -6s; }}
    .st-key-card_8 {{ right: 18%;  top: 70%; animation-delay: -2.5s; }}

    /* The wide card sits centred, just above the question box. */
    .st-key-learn {{
        position: absolute;
        left: 0; right: 0; top: 71.5%;
        margin: 0 auto;
        width: clamp(17rem, 27cqw, 22rem);
        z-index: 2;
        animation: card-drift 8s ease-in-out infinite;
        animation-delay: -4s;
    }}
}}
/* On a smaller main area the cards are narrow, so their text wraps and
   they grow tall. Dropping the small icons gives the text room, and the
   two bottom cards move out and up to leave space for the wide card. */
@container main (min-width: 700px) and (max-width: 1000px) {{
    [class*="st-key-card_"] button [data-testid="stIconMaterial"] {{ display: none; }}
    [class*="st-key-card_"] {{ width: clamp(8.6rem, 19cqw, 12rem); }}
    .st-key-card_7 {{ left: 4%;  top: 68%; }}
    .st-key-card_8 {{ right: 4%; top: 69%; }}
    .st-key-card_5 {{ top: 50%; }}
    .st-key-card_6 {{ top: 51%; }}
    .st-key-learn {{ top: 70%; }}
}}
}}
/* People who ask their computer for less motion get still cards. */
@media (prefers-reduced-motion: reduce) {{
    [class*="st-key-card_"], .st-key-learn {{ animation: none !important; }}
}}

/* The wide "Learn how it works" card: a dark icon tile on the left, one
   line of larger text, an arrow on the right. */
.st-key-learn {{ display: flex; justify-content: center; margin-top: 1rem; }}
.st-key-learn button {{
    position: relative;
    width: 100%;
    background: {GLASS};
    border: 1px solid {GLASS_EDGE};
    border-radius: 16px;
    padding: 0.7rem 2.4rem 0.7rem 0.8rem;
    justify-content: flex-start;
    backdrop-filter: blur(6px);
    transition: background 120ms ease, transform 120ms ease;
}}
.st-key-learn button:hover {{
    background: {GLASS_STRONG};
    border-color: #ffffff;
    transform: translateY(-2px);
}}
.st-key-learn button > div {{ justify-content: flex-start; width: 100%; }}
.st-key-learn button > div > span {{ gap: 0.8rem; align-items: center; }}
/* Streamlit fixes a button icon at 16 pixels; the tile needs its own size. */
.st-key-learn button span:has(> [data-testid="stIconMaterial"]) {{
    width: auto; height: auto; overflow: visible; flex-shrink: 0;
}}
.st-key-learn button [data-testid="stIconMaterial"] {{
    background: #1c1c1a;
    color: #ffffff;
    border-radius: 10px;
    width: 2.5rem; height: 2.5rem;
    min-width: 2.5rem;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem;
    box-sizing: border-box;
}}
.st-key-learn button [data-testid="stMarkdownContainer"] {{
    white-space: nowrap !important; overflow: visible !important;
}}
.st-key-learn button p {{
    font-size: clamp(0.95rem, 1.7cqw, 1.25rem);
    font-weight: 500;
    letter-spacing: -0.01em;
    color: #1c1c1a;
}}
.st-key-learn button p strong {{ font-weight: 700; }}
.st-key-learn button::after {{
    content: "\\2197";
    position: absolute; right: 1rem; top: 50%;
    transform: translateY(-50%);
    color: #8a8880; font-size: 0.95rem;
}}

/* Sidebar: frosted like the rest, with conversation titles on one line,
   aligned left. */
[data-testid="stSidebar"] {{
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(14px);
    border-right: 1px solid {GLASS_EDGE};
}}
[class*="st-key-open_"] button {{ justify-content: flex-start; text-align: left; }}
[class*="st-key-open_"] button > div {{ justify-content: flex-start; width: 100%; }}

/* Chat bubbles and the question box. */
[data-testid="stChatMessage"] {{
    background: {GLASS};
    border: 1px solid {GLASS_EDGE};
    border-radius: 14px;
    backdrop-filter: blur(6px);
}}
[data-testid="stChatInput"] > div {{
    background: {GLASS_STRONG};
    border: 1px solid {GLASS_EDGE};
    border-radius: 18px;
}}

/* A report sits on a more solid panel so tables stay easy to read. */
[class*="st-key-report_panel_"] {{
    background: {GLASS_STRONG};
    border: 1px solid {GLASS_EDGE};
    border-radius: 14px;
    padding: 1rem 1.25rem;
}}

/* --- the "How it works" guide ------------------------------------------- */

/* While the guide is open the page column is wider, so five step cards
   fit comfortably in one row. */
[data-testid="stMainBlockContainer"]:has(.gw-question) {{ max-width: 62rem; }}

/* The question, as a dark bubble on the right. */
.gw-question {{ display: flex; justify-content: flex-end; margin: 0.4rem 0 0.2rem; }}
.gw-question span {{
    background: #1c1c1a; color: #ffffff;
    border-radius: 14px; padding: 0.55rem 1rem;
    font-weight: 600; font-size: 0.95rem;
}}

/* The answer panel. */
[class*="st-key-guide_panel_"] {{
    background: rgba(255, 255, 255, 0.62);
    border: 1px solid {GLASS_EDGE};
    border-radius: 18px;
    padding: 1.1rem 1.25rem 1.2rem;
    backdrop-filter: blur(6px);
    margin-bottom: 0.6rem;
}}

/* The row of numbered step cards, joined by small arrows. */
.gw-steps {{
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 1.1rem;
}}
.gw-step {{
    position: relative;
    background: rgba(255, 255, 255, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.95);
    border-radius: 12px;
    padding: 0.7rem 0.7rem 0.8rem;
}}
.gw-step:not(:last-child)::after {{
    content: "\\203A";
    position: absolute; right: -0.85rem; top: 36%;
    color: #8a8880; font-size: 1.2rem;
}}
.gw-num {{
    width: 1.35rem; height: 1.35rem; border-radius: 50%;
    background: #1c1c1a; color: #ffffff;
    font-size: 0.72rem; font-weight: 600;
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 0.4rem;
}}
.gw-step-title {{ font-weight: 600; font-size: 0.92rem; line-height: 1.25; margin-bottom: 0.15rem; }}
.gw-step-line {{ color: #55544f; font-size: 0.8rem; line-height: 1.35; }}
.gw-tag {{
    display: inline-block;
    border: 1px solid rgba(0, 0, 0, 0.16); border-radius: 10px;
    padding: 0 0.4rem; margin: 0.35rem 0.25rem 0 0;
    font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
    font-size: 0.7rem; color: #44443f;
    background: rgba(255, 255, 255, 0.5);
}}
.gw-dot {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 1.15rem; height: 1.15rem; border-radius: 50%;
    border: 1px solid rgba(0, 0, 0, 0.18);
    margin: 0.35rem 0.18rem 0 0;
    font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
    font-size: 0.64rem; color: #55544f;
}}
/* On a narrow panel five cards do not fit in one row: wrap, without arrows. */
@container main (max-width: 820px) {{
    .gw-steps {{ grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 0.6rem; }}
    .gw-step::after {{ display: none; }}
}}

/* The follow-up chips under the panel. */
[class*="st-key-chip_"] button {{
    background: rgba(255, 255, 255, 0.6);
    border: 1px solid {GLASS_EDGE};
    border-radius: 14px;
    backdrop-filter: blur(6px);
}}
[class*="st-key-chip_"] button:hover {{ background: {GLASS_STRONG}; border-color: #ffffff; }}
.st-key-chip_back button {{ background: transparent; border: none; }}
</style>
"""


def apply_styles() -> None:
    """Add the app's CSS to the page."""
    st.html(CSS)
