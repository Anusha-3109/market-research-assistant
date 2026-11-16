"""Tests for the two approval points, with fake models and no internet.

1. The competitor review inside the report workflow.
2. The approval before a report is saved to a file.
"""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

import main
from agent import approval
from agent.agent import assemble_agent, pending_pause, resume_steps, stream_steps
from agent.approval import Pause, review_answer, save_answer
from agent.report import review
from agent.report.deps import Deps
from agent.report.graph import build_report_graph
from agent.report.state import (
    Candidate,
    CandidateList,
    Competitor,
    MarketFigureList,
    NewsList,
    PriceList,
    Rejection,
    ResearchBrief,
    Swot,
    TermCheck,
    Verdict,
)

BRIEF = ResearchBrief(
    local_language="German", category_terms=["Kochbox"],
    competitor_query="Kochbox Anbieter Deutschland",
    market_query="Kochbox Markt Deutschland", price_word="Preise",
    trend_terms=["Kochbox", "Fertiggerichte", "Essenslieferung"])
SWOT = Swot(strengths=["a", "b"], weaknesses=["a", "b"],
            opportunities=["a", "b"], threats=["a", "b"])


def competitor(name: str, shop: str = "") -> Competitor:
    return Competitor(name=name, shop_url=shop or f"https://{name.lower()}.example",
                      evidence_url=f"https://list.example/{name}",
                      reason="sells meal kits", offer="Meal kits")


STATE = {
    "product": "meal kits", "country": "Germany",
    "competitors": [competitor("Alpha"), competitor("Beta"), competitor("Gamma")],
    "verified": [competitor("Alpha"), competitor("Beta"), competitor("Gamma"),
                 competitor("Delta")],
    "rejected": [Rejection(name="Omega", reason="not active in Germany")],
}


def search_deps(results: list[dict] | None = None, searched: list | None = None) -> Deps:
    def search(query):
        if searched is not None:
            searched.append(query)
        return results or []

    return Deps(ask=None, search=search, news=None, read_page=None,
                financials=None, trend=None)


def names(update: dict) -> list[str]:
    return [c.name for c in update["competitors"]]


# --- what the user is shown --------------------------------------------------------------

def test_the_review_shows_chosen_left_out_and_dropped_companies():
    request = review.review_request(STATE)

    assert request["kind"] == "competitor_review"
    assert [c["name"] for c in request["competitors"]] == ["Alpha", "Beta", "Gamma"]
    assert request["competitors"][0]["website"] == "https://alpha.example"
    assert request["left_out"] == ["Delta"]
    assert request["dropped"] == [{"name": "Omega", "reason": "not active in Germany"}]


# --- applying the user's decision ----------------------------------------------------------

def test_approve_leaves_the_list_unchanged():
    update = review.apply_review(STATE, review_answer("approve"), search_deps())

    assert "competitors" not in update            # nothing to change
    assert update["log"] == ["Review: the user approved the competitor list"]


def test_cancel_marks_the_report_as_cancelled():
    update = review.apply_review(STATE, review_answer("cancel"), search_deps())

    assert update["cancelled"] is True


def test_removing_a_company_takes_it_out_whatever_the_letter_case():
    update = review.apply_review(STATE, review_answer("edit", remove=["beta"]), search_deps())

    assert names(update) == ["Alpha", "Gamma"]
    assert update["log"] == ["Review: removed Beta"]


def test_adding_a_company_that_was_verified_but_left_out_reuses_its_record():
    searched = []
    update = review.apply_review(STATE, review_answer("edit", add=["Delta"]),
                                 search_deps(searched=searched))

    assert names(update) == ["Alpha", "Beta", "Gamma", "Delta"]
    assert update["competitors"][-1].shop_url == "https://delta.example"
    assert searched == []                          # no search was needed


def test_adding_an_unknown_company_looks_up_its_own_website():
    pages = [{"url": "https://blog.example/marley-spoon-review"},
             {"url": "https://marleyspoon.de/"}]

    update = review.apply_review(STATE, review_answer("edit", add=["Marley Spoon"]),
                                 search_deps(pages))

    added = update["competitors"][-1]
    assert added.name == "Marley Spoon"
    assert added.shop_url == "https://marleyspoon.de"
    assert added.offer == "Added by you"


def test_an_added_company_without_its_own_site_keeps_a_page_about_it_as_evidence():
    pages = [{"url": "https://blog.example/tiny-meals-review"}]

    added = review.apply_review(STATE, review_answer("edit", add=["Tiny Meals"]),
                                search_deps(pages))["competitors"][-1]

    assert added.shop_url == ""
    assert added.evidence_url == "https://blog.example/tiny-meals-review"


def test_a_company_nothing_is_known_about_is_not_added_and_the_log_says_so():
    update = review.apply_review(STATE, review_answer("edit", add=["Ghost Foods"]),
                                 search_deps([]))

    assert names(update) == ["Alpha", "Beta", "Gamma"]
    assert update["log"] == ["Review: Ghost Foods not added (no information found about it)"]


def test_adding_a_company_that_is_already_listed_changes_nothing():
    update = review.apply_review(STATE, review_answer("edit", add=["alpha"]), search_deps())

    assert names(update) == ["Alpha", "Beta", "Gamma"]


def test_removing_and_adding_in_one_decision():
    update = review.apply_review(
        STATE, review_answer("edit", remove=["Gamma"], add=["Delta"]), search_deps())

    assert names(update) == ["Alpha", "Beta", "Delta"]


def test_no_more_companies_are_added_once_the_limit_is_reached(monkeypatch):
    monkeypatch.setattr(review, "REPORT_MAX_AFTER_REVIEW", 3)

    update = review.apply_review(STATE, review_answer("edit", add=["Delta"]), search_deps())

    assert names(update) == ["Alpha", "Beta", "Gamma"]
    assert "limit of 3" in update["log"][0]


# --- typed answers in the terminal ------------------------------------------------------------

LISTED = ["Alpha", "Beta", "Gamma"]


def test_a_typed_review_answer_is_understood():
    parse = approval.parse_review_reply

    assert parse("approve", LISTED) == {"action": "approve"}
    assert parse("cancel", LISTED) == {"action": "cancel"}
    assert parse("remove 2", LISTED) == {"action": "edit", "remove": ["Beta"], "add": []}
    assert parse("remove 1, 3", LISTED) == {"action": "edit", "remove": ["Alpha", "Gamma"], "add": []}
    assert parse("remove Beta", LISTED) == {"action": "edit", "remove": ["Beta"], "add": []}
    assert parse("add Marley Spoon", LISTED) == {
        "action": "edit", "remove": [], "add": ["Marley Spoon"]}
    assert parse("remove 3; add Delta, Marley Spoon", LISTED) == {
        "action": "edit", "remove": ["Gamma"], "add": ["Delta", "Marley Spoon"]}


def test_a_number_that_is_not_in_the_list_is_ignored():
    assert approval.parse_review_reply("remove 9", LISTED) == {"action": "approve"}


def test_a_typed_save_answer_is_understood():
    parse = approval.parse_save_reply

    assert parse("approve") == save_answer("approve")
    assert parse("yes") == save_answer("approve")
    assert parse("reject") == save_answer("reject")
    assert parse("title My report") == save_answer("edit", "My report")


def test_an_unclear_save_answer_counts_as_reject():
    # Saving writes a file, so anything unclear must not be taken as a yes.
    assert approval.parse_save_reply("hmm maybe") == save_answer("reject")
    assert approval.parse_save_reply("") == save_answer("reject")


def test_a_save_pause_shows_the_file_that_would_be_written():
    pause = approval.read_pause({"action_requests": [
        {"name": "save_report", "args": {"title": "Meal kits: Germany!"}}]})

    assert pause.kind == "save_approval"
    assert pause.data["filename"].startswith("reports/")
    assert pause.data["filename"].endswith("-meal-kits-germany.md")


def test_something_that_is_not_one_of_our_pauses_is_ignored():
    assert approval.read_pause("just text") is None
    assert approval.read_pause({"action_requests": [{"name": "other_tool", "args": {}}]}) is None


def test_the_terminal_describes_both_kinds_of_pause():
    review_text = main.describe_pause(Pause("competitor_review", review.review_request(STATE)))
    save_text = main.describe_pause(Pause("save_approval", {"title": "T", "filename": "reports/t.md"}))

    assert "1. Alpha  (https://alpha.example)" in review_text
    assert "Verified but left out: Delta" in review_text
    assert "Dropped: Omega" in review_text
    assert "Save this report as reports/t.md?" in save_text


# --- the whole thing through the chat agent ---------------------------------------------------------

class ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def workflow_deps(calls: list) -> Deps:
    """Fake research: two candidates that are both verified."""
    def ask(schema, instructions, material):
        calls.append(schema.__name__)
        if schema is ResearchBrief:
            return BRIEF
        if schema is CandidateList:
            return CandidateList(candidates=[
                Candidate(name="Alpha", mentioned_at="https://alpha.example"),
                Candidate(name="Beta", mentioned_at="https://beta.example")])
        if schema is Verdict:
            company = "alpha" if "'Alpha'" in instructions else "beta"
            return Verdict(sells_this_product=True, operates_in_country=True,
                           shop_url=f"https://{company}.example",
                           evidence_url=f"https://{company}.example",
                           reason="sells meal kits", offer="Meal kits")
        if schema is PriceList:
            return PriceList(prices=[])
        if schema is MarketFigureList:
            return MarketFigureList(figures=[])
        if schema is NewsList:
            return NewsList(items=[])
        if schema is TermCheck:
            return TermCheck(specific=True, reason="test")
        return SWOT

    pages = [{"title": "Alpha", "url": "https://alpha.example", "content": "Alpha meal kits"},
             {"title": "Beta", "url": "https://beta.example", "content": "Beta meal kits"}]
    return Deps(ask=ask, search=lambda query: pages, news=lambda query: [],
                read_page=lambda url: None, financials=lambda name: None,
                trend=lambda term, country: None)


def report_agent(calls: list, saved: list | None = None, replies: list | None = None):
    """A chat agent whose report tool runs the real workflow (with fake
    research) and whose save tool only records what it was asked to save."""
    graph = build_report_graph(workflow_deps(calls), review=True)

    @tool("create_market_report", return_direct=True)
    def create_market_report(product: str, country: str) -> str:
        """Report."""
        final = graph.invoke({"product": product, "country": country})
        return "CANCELLED" if final.get("cancelled") else final["report"]

    @tool
    def save_report(title: str) -> str:
        """Save."""
        if saved is not None:
            saved.append(title)
        return f"Report saved as {title}"

    ask_report = AIMessage("", tool_calls=[{
        "name": "create_market_report", "id": "r1",
        "args": {"product": "meal kits", "country": "Germany"}}])
    model = ScriptedModel(messages=iter(replies if replies is not None else [ask_report]))
    return assemble_agent(model, [], tools=[create_market_report, save_report],
                          checkpointer=InMemorySaver())


def last_pause(items: list) -> Pause | None:
    return next((item for item in reversed(items) if isinstance(item, Pause)), None)


def report_text(items: list) -> str:
    return next(item.content for item in items if isinstance(item, ToolMessage))


def test_the_workflow_pauses_with_the_competitor_list_before_any_research():
    calls = []
    agent = report_agent(calls)

    items = list(stream_steps(agent, "Report on meal kits in Germany", "t1"))

    pause = last_pause(items)
    assert pause.kind == "competitor_review"
    assert [c["name"] for c in pause.data["competitors"]] == ["Alpha", "Beta"]
    assert "PriceList" not in calls and "Swot" not in calls   # research has not started


def test_approving_continues_to_a_full_report():
    agent = report_agent([])
    list(stream_steps(agent, "Report on meal kits in Germany", "t1"))

    items = list(resume_steps(agent, review_answer("approve"), "t1"))

    report = report_text(items)
    assert "| Alpha |" in report and "| Beta |" in report
    assert last_pause(items) is None


def test_a_removed_competitor_is_not_in_the_report():
    agent = report_agent([])
    list(stream_steps(agent, "Report on meal kits in Germany", "t1"))

    items = list(resume_steps(agent, review_answer("edit", remove=["Beta"]), "t1"))

    report = report_text(items)
    assert "| Alpha |" in report
    assert "| Beta |" not in report


def test_cancelling_stops_the_workflow_without_doing_the_research():
    calls = []
    agent = report_agent(calls)
    list(stream_steps(agent, "Report on meal kits in Germany", "t1"))

    items = list(resume_steps(agent, review_answer("cancel"), "t1"))

    assert report_text(items) == "CANCELLED"
    assert "PriceList" not in calls and "Swot" not in calls


def test_resuming_does_not_repeat_the_search_for_competitors():
    calls = []
    agent = report_agent(calls)
    list(stream_steps(agent, "Report on meal kits in Germany", "t1"))
    before = calls.count("CandidateList"), calls.count("Verdict")

    list(resume_steps(agent, review_answer("approve"), "t1"))

    assert (calls.count("CandidateList"), calls.count("Verdict")) == before


def test_a_waiting_conversation_can_be_found_again_later():
    agent = report_agent([])
    list(stream_steps(agent, "Report on meal kits in Germany", "t1"))

    assert pending_pause(agent, "t1").kind == "competitor_review"
    assert pending_pause(agent, "another-conversation") is None


# --- approval before saving -----------------------------------------------------------------------

SAVE_CALL = AIMessage("", tool_calls=[{"name": "save_report", "id": "s1",
                                       "args": {"title": "Meal kits Germany"}}])


def save_agent(saved: list):
    return report_agent([], saved=saved, replies=[SAVE_CALL, AIMessage("Done.")])


def test_saving_pauses_and_writes_nothing_until_the_user_decides():
    saved = []
    agent = save_agent(saved)

    items = list(stream_steps(agent, "Save this report", "t1"))

    assert last_pause(items).kind == "save_approval"
    assert last_pause(items).data["title"] == "Meal kits Germany"
    assert saved == []


def test_approving_the_save_runs_it():
    saved = []
    agent = save_agent(saved)
    list(stream_steps(agent, "Save this report", "t1"))

    list(resume_steps(agent, save_answer("approve"), "t1"))

    assert saved == ["Meal kits Germany"]


def test_changing_the_title_saves_under_the_new_title():
    saved = []
    agent = save_agent(saved)
    list(stream_steps(agent, "Save this report", "t1"))

    list(resume_steps(agent, save_answer("edit", "My own title"), "t1"))

    assert saved == ["My own title"]


def test_rejecting_the_save_writes_nothing_and_tells_the_agent():
    saved = []
    agent = save_agent(saved)
    list(stream_steps(agent, "Save this report", "t1"))

    items = list(resume_steps(agent, save_answer("reject"), "t1"))

    assert saved == []
    told = next(item for item in items if isinstance(item, ToolMessage))
    assert "declined to save" in told.content


def test_without_a_checkpointer_there_is_no_approval_step():
    # No saved conversation to come back to, so the agent must not pause.
    saved = []

    @tool
    def save_report(title: str) -> str:
        """Save."""
        saved.append(title)
        return "saved"

    model = ScriptedModel(messages=iter([SAVE_CALL, AIMessage("Done.")]))
    agent = assemble_agent(model, [], tools=[save_report])

    agent.invoke({"messages": [{"role": "user", "content": "Save this report"}]})

    assert saved == ["Meal kits Germany"]
