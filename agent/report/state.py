"""The data that moves through the report workflow.

Two kinds of definitions live here:

- Pydantic models describe what the language model must return at a step.
  The model is forced to fill in exactly these fields ("structured output"),
  so the code can check the answer.
- ReportState is the shared memory of the workflow. Each step reads what it
  needs from it and returns the fields it wants to add or change.
"""

import operator
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field


# --- step 1: what the user wants ---------------------------------------------------

class ResearchBrief(BaseModel):
    """The research request, prepared for searching."""

    local_language: str = Field(
        description="The main language of the target country, in English, "
                    "for example 'German'.")
    category_terms: list[str] = Field(
        description="2 or 3 short terms (1 or 2 words each) that people in "
                    "the target country type into a search engine for this "
                    "product category, in the local language. Specific to "
                    "the product: for meal kits in Germany 'Kochbox', never "
                    "a general word like 'Essen'.")
    competitor_query: str = Field(
        description="One search query in the local language that finds "
                    "companies selling this product in the target country, "
                    "for example 'Kochbox Anbieter Deutschland'.")
    market_query: str = Field(
        description="One search query in the local language for the size of "
                    "this market in the target country, for example "
                    "'Kochbox Markt Deutschland Umsatz'.")
    price_word: str = Field(
        description="The local-language word for 'prices', for example "
                    "'Preise'.")
    trend_terms: list[str] = Field(
        description="3 nouns, most common first, that name this product "
                    "category in the local language: the word a shopper "
                    "types to find a provider, for example 'Kochbox', "
                    "'Fertiggerichte' or 'Essenslieferung' for meal delivery "
                    "in Germany. Test each word: would most people who "
                    "search for it be looking to buy this product? Reject "
                    "adjectives and broad words such as 'Bio', 'gesund', "
                    "'Essen' or 'Mahlzeit'. One word each, no phrases.")


# --- step 2: companies that might be competitors -------------------------------------

class Candidate(BaseModel):
    """A company named in the search results."""

    name: str = Field(description="The brand name, without legal form, for "
                                  "example 'HelloFresh'.")
    mentioned_at: str = Field(description="The URL of the search result that "
                                          "names this company. Copy it exactly.")


class CandidateList(BaseModel):
    candidates: list[Candidate]


# --- step 3: is a candidate really a competitor? ---------------------------------------

class Verdict(BaseModel):
    """The model's judgement on one candidate, based on search results."""

    sells_this_product: bool = Field(
        description="True only if this product category is the company's "
                    "main offer. False for neighbouring categories.")
    operates_in_country: bool = Field(
        description="True only if the results show the company sells to "
                    "customers in the target country: a shop on a domain or "
                    "page for that country, or a clear statement. False if "
                    "the results only show activity in other countries.")
    shop_url: str = Field(
        description="The URL of the company's own shop or website for the "
                    "target country, copied exactly from the results. Empty "
                    "if no result is the company's own site.")
    evidence_url: str = Field(
        description="The URL of the result that best supports the two "
                    "answers above, copied exactly.")
    offer: str = Field(
        default="",
        description="What the company sells, in at most 10 words, for "
                    "example 'Frozen high-protein ready meals'.")
    reason: str = Field(description="One sentence explaining the verdict.")


class Competitor(BaseModel):
    """A candidate that passed verification."""

    name: str
    shop_url: str        # the company's own site for the country, or ""
    evidence_url: str    # where it was confirmed
    reason: str
    offer: str = ""      # what the company sells, in a few words


class Rejection(BaseModel):
    """A candidate that was dropped, and why. Kept so the decision can be
    shown to the user."""

    name: str
    reason: str


# --- steps 4 and 5: one competitor in detail ------------------------------------------------

class PricePoint(BaseModel):
    product: str = Field(description="The product or plan the price is for.")
    price: str = Field(description="The price exactly as written on the "
                                   "page, with its currency, for example "
                                   "'€7.99 per meal'.")


class PriceList(BaseModel):
    prices: list[PricePoint]


class CompetitorProfile(BaseModel):
    """Everything collected about one competitor."""

    name: str
    shop_url: str
    figures: str             # text from the financials lookup, or "" if none
    figures_source: str      # link the figures came from, or ""
    prices: list[PricePoint]
    price_source: str        # the page the prices were read from, set by code
    price_note: str          # why there are no prices, when there are none


# --- step 6: the market --------------------------------------------------------------------

class MarketFigure(BaseModel):
    statement: str = Field(description="What the figure measures, in a few "
                                       "words, for example 'meal kit market "
                                       "revenue'.")
    value: str = Field(description="The figure exactly as written, with its "
                                   "unit, for example 'USD 1.2 billion'.")
    area: str = Field(description="The area the figure covers, as the source "
                                  "states it, for example 'Germany', "
                                  "'Europe' or 'worldwide'.")
    scope: str = Field(description="One of: 'country' if the figure is for "
                                   "the target country only, 'wider' if it "
                                   "covers a larger region or the world, "
                                   "'other' if it is for a different country.")
    year: str = Field(description="The year the figure refers to, or "
                                  "'not stated'.")
    source_url: str = Field(description="The URL of the result the figure "
                                        "comes from, copied exactly.")


class MarketFigureList(BaseModel):
    figures: list[MarketFigure]


# --- step 7: news and demand ------------------------------------------------------------------

class NewsItem(BaseModel):
    summary: str = Field(description="One sentence on what happened.")
    date: str = Field(description="The publication date as shown in the "
                                  "result, or 'not stated'.")
    source_url: str = Field(description="The URL of the result, copied exactly.")


class NewsList(BaseModel):
    items: list[NewsItem]


class TermCheck(BaseModel):
    """Is a search word specific enough to measure demand for a product?"""

    specific: bool = Field(description="True only if most people searching "
                                       "this word want this product.")
    reason: str = Field(description="One short sentence.")


class TrendResult(BaseModel):
    term: str          # the search word that was measured
    summary: str       # direction, figures and source, as text
    reliable: bool     # False when there were too few searches to trust it


# --- step 8: the analysis ------------------------------------------------------------------------

class Swot(BaseModel):
    """The model's own analysis. Each list has 2 to 4 short points."""

    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]


def merge_titles(first: dict | None, second: dict | None) -> dict:
    """Join two address -> title dictionaries. Used when parallel branches
    each return the titles of the pages they found."""
    return {**(first or {}), **(second or {})}


# --- the workflow's shared memory ------------------------------------------------------

class ReportState(TypedDict, total=False):
    # The request.
    product: str
    country: str
    idea: str
    # The answer style chosen in the app; it shapes the SWOT's wording only.
    style: str

    # Step 1.
    brief: ResearchBrief

    # Step 2.
    candidates: list[Candidate]

    # Step 3. Candidates are verified in parallel; operator.add tells
    # LangGraph to join the lists the parallel branches return.
    verified: Annotated[list[Competitor], operator.add]
    rejected: Annotated[list[Rejection], operator.add]
    competitors: list[Competitor]

    # Set when the user cancels at the competitor review.
    cancelled: bool

    # Steps 4 and 5, one parallel branch per competitor.
    profiles: Annotated[list[CompetitorProfile], operator.add]

    # Steps 6 and 7.
    market_figures: list[MarketFigure]
    news: list[NewsItem]
    trend: TrendResult | None

    # Steps 8 and 9.
    swot: Swot | None
    swot_attempts: int
    report: str            # the finished report text
    problems: list[str]    # what the report check found, empty if it passed

    # The titles of pages found along the way (address -> title), so the
    # app can name each source. It plays no part in the research itself.
    titles: Annotated[dict[str, str], merge_titles]

    # One line per step, for showing progress.
    log: Annotated[list[str], operator.add]


# Every model class that can appear in the workflow state. The checkpointer
# is told about them so it can save and load a paused workflow.
STATE_MODELS = [
    ResearchBrief, Candidate, Verdict, Competitor, Rejection, PricePoint,
    CompetitorProfile, MarketFigure, NewsItem, TrendResult, Swot,
]
