"""The steps of the report workflow.

Each step is a function that takes the workflow state and returns the
fields it adds. make_steps() builds them around the model and search they
should use.

The pattern in every step is the same:
1. code gathers material (runs searches),
2. the model does one narrow job on that material and answers in a fixed
   shape,
3. code checks the answer before it is accepted.
"""

import re
import unicodedata
from urllib.parse import urlsplit

from agent.config import REPORT_MAX_CANDIDATES, REPORT_MAX_COMPETITORS
from agent.countries import find_country
from agent.report.deps import Deps
from agent.report.state import (
    Candidate,
    CandidateList,
    Competitor,
    Rejection,
    ReportState,
    ResearchBrief,
    Verdict,
)
from agent.tools import format_results


# --- small helpers -----------------------------------------------------------------

def clean_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def known_url(url: str, results: list[dict]) -> bool:
    """True if the URL really is one of the search results. The model is
    told to copy URLs exactly; this catches an invented or altered one."""
    return bool(url) and clean_url(url) in {clean_url(r.get("url", "")) for r in results}


def name_key(name: str) -> str:
    """Reduce a name to plain lower-case letters and digits, so that
    'Löwenanteil', 'Lowenanteil' and 'LÖWENANTEIL' compare equal."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plain.lower())


def is_own_site(name: str, url: str) -> bool:
    """True if the web address belongs to the company: its host contains
    the brand name. German umlauts are also tried in their written-out form
    (ö -> oe), as in loewenanteil.com."""
    host = re.sub(r"[^a-z0-9]", "", (urlsplit(url).hostname or "").lower())
    spelled_out = name.lower().translate(str.maketrans(
        {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    keys = {name_key(name), name_key(spelled_out)} - {""}
    return any(key in host for key in keys)


def count_mentions(name: str, results: list[dict]) -> int:
    """How many search results mention the company, by title or extract."""
    key = name_key(name)
    return sum(
        1 for result in results
        if key in name_key(f"{result.get('title', '')} {result.get('content', '')}")
    )


def merge_results(result_lists: list[list[dict]]) -> list[dict]:
    """Join several result lists, dropping pages that appear twice."""
    seen, merged = set(), []
    for results in result_lists:
        for result in results:
            url = clean_url(result.get("url", ""))
            if url and url not in seen:
                seen.add(url)
                merged.append(result)
    return merged


# --- the steps ----------------------------------------------------------------------

def make_steps(deps: Deps) -> dict:
    """Build the step functions around a model and a search."""

    def understand_request(state: ReportState) -> dict:
        """Step 1: turn the request into search words in the local language."""
        found = find_country(state["country"])
        country = found.name if found else state["country"]

        brief = deps.ask(
            ResearchBrief,
            "You prepare a market research request for searching. Fill in "
            "the fields for the product and country given.",
            f"Product or industry: {state['product']}\nTarget country: {country}",
        )
        return {
            "country": country,
            "brief": brief,
            "log": [f"Search terms ({brief.local_language}): "
                    f"{', '.join(brief.category_terms)}"],
        }

    def find_candidates(state: ReportState) -> dict:
        """Step 2: search for companies and list the ones that are named."""
        product, country, brief = state["product"], state["country"], state["brief"]
        queries = [
            brief.competitor_query,
            f"{product} companies {country}",
            f"best {product} {country}",
        ]
        results = merge_results([deps.search(query) for query in queries])
        if not results:
            return {"candidates": [], "log": ["No search results for competitors"]}

        answer = deps.ask(
            CandidateList,
            f"List the companies that these search results name as sellers of "
            f"{product} in {country}. Only list companies named in the "
            f"results. Do not add companies from memory. Do not list market "
            f"research firms, news sites or comparison sites. At most "
            f"{REPORT_MAX_CANDIDATES} companies, most prominent first.",
            format_results(results),
        )

        # Keep one entry per company, and only those the results really name.
        candidates, seen = [], set()
        for candidate in answer.candidates:
            key = name_key(candidate.name)
            if not key or key in seen or not known_url(candidate.mentioned_at, results):
                continue
            seen.add(key)
            candidates.append(candidate)

        # Rank by how many search results mention each company, counted in
        # code. The model's own ordering put the market leader sixth.
        candidates.sort(key=lambda c: count_mentions(c.name, results), reverse=True)
        candidates = candidates[:REPORT_MAX_CANDIDATES]

        return {
            "candidates": candidates,
            "log": [f"Candidates found: {', '.join(c.name for c in candidates) or 'none'}"],
        }

    def verify_competitor(task: dict) -> dict:
        """Step 3, run once per candidate: check that the company sells
        this product in this country."""
        candidate: Candidate = task["candidate"]
        product, country = task["product"], task["country"]
        name = candidate.name

        results = merge_results([
            deps.search(f"{name} {country}"),
            deps.search(f"{name} {task['category_term']}"),
        ])
        if not results:
            return {"rejected": [Rejection(name=name, reason="no search results")]}

        verdict: Verdict = deps.ask(
            Verdict,
            f"Decide whether the company '{name}' is a direct competitor for "
            f"someone selling {product} in {country}. Judge only from the "
            f"search results given. If the results do not show it, answer "
            f"false.",
            format_results(results),
        )

        if not verdict.sells_this_product:
            return {"rejected": [Rejection(name=name,
                                           reason=f"different product: {verdict.reason}")]}
        if not verdict.operates_in_country:
            return {"rejected": [Rejection(name=name,
                                           reason=f"not active in {country}: {verdict.reason}")]}

        # Code checks on the model's answer.
        shop_url = verdict.shop_url
        if not (known_url(shop_url, results) and is_own_site(name, shop_url)):
            shop_url = ""
        evidence_url = verdict.evidence_url if known_url(verdict.evidence_url, results) else shop_url
        if not evidence_url:
            return {"rejected": [Rejection(
                name=name, reason="no page among the results supports the verdict")]}

        return {"verified": [Competitor(name=name, shop_url=clean_url(shop_url),
                                        evidence_url=clean_url(evidence_url),
                                        reason=verdict.reason)]}

    def select_competitors(state: ReportState) -> dict:
        """Put the verified companies back in the order they were found
        (most prominent first) and keep the top few."""
        order = {name_key(c.name): position
                 for position, c in enumerate(state.get("candidates", []))}
        verified = sorted(state.get("verified", []),
                          key=lambda c: order.get(name_key(c.name), len(order)))
        competitors = verified[:REPORT_MAX_COMPETITORS]

        log = [f"Confirmed competitors: {', '.join(c.name for c in competitors) or 'none'}"]
        for extra in verified[REPORT_MAX_COMPETITORS:]:
            log.append(f"Confirmed but left out (limit of {REPORT_MAX_COMPETITORS}): {extra.name}")
        for rejection in state.get("rejected", []):
            log.append(f"Dropped {rejection.name}: {rejection.reason}")
        return {"competitors": competitors, "log": log}

    return {
        "understand_request": understand_request,
        "find_candidates": find_candidates,
        "verify_competitor": verify_competitor,
        "select_competitors": select_competitors,
    }
