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
    reason: str = Field(description="One sentence explaining the verdict.")


class Competitor(BaseModel):
    """A candidate that passed verification."""

    name: str
    shop_url: str        # the company's own site for the country, or ""
    evidence_url: str    # where it was confirmed
    reason: str


class Rejection(BaseModel):
    """A candidate that was dropped, and why. Kept so the decision can be
    shown to the user."""

    name: str
    reason: str


# --- the workflow's shared memory ------------------------------------------------------

class ReportState(TypedDict, total=False):
    # The request.
    product: str
    country: str
    idea: str

    # Step 1.
    brief: ResearchBrief

    # Step 2.
    candidates: list[Candidate]

    # Step 3. Candidates are verified in parallel; operator.add tells
    # LangGraph to join the lists the parallel branches return.
    verified: Annotated[list[Competitor], operator.add]
    rejected: Annotated[list[Rejection], operator.add]
    competitors: list[Competitor]

    # One line per step, for showing progress.
    log: Annotated[list[str], operator.add]
