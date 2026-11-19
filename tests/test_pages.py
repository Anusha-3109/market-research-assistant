"""Tests for the pages of the app: links in the sidebar, and the "How it
works" page.

Research is the app as it was; the other pages are opened from the links
at the top of the sidebar. The Admin link is shown only to an admin.
"""

from unittest.mock import patch

from tests.test_app import button, page  # noqa: F401  (page is a fixture)
from tests.test_language import switch


def page_links(app) -> list[str]:
    return [b.label for b in app.sidebar.button if (b.key or "").startswith("page_")]


def open_page(app, name):
    button(app, f"page_{name}").click().run()
    assert not app.exception
    return app


def html(app) -> str:
    return "\n".join(element.proto.body for element in app.get("html"))


def markdown(app) -> str:
    return "\n".join(m.value for m in app.markdown)


# --- the links -----------------------------------------------------------------------------------

def test_the_sidebar_links_to_the_pages_and_research_is_open_at_first(page):  # noqa: F811
    app = page()

    assert page_links(app) == ["Research", "Dashboard", "How it works", "Admin"]
    assert button(app, "page_research").proto.type == "secondary"       # the open one is marked


def test_a_visitor_who_is_not_an_admin_has_no_admin_link(page):  # noqa: F811
    with patch("ui.pages.is_admin", lambda account: False):
        app = page()

    assert "Admin" not in page_links(app)


def test_back_to_research_shows_the_start_screen_again(page):  # noqa: F811
    app = open_page(page(), "how")

    open_page(app, "research")

    assert any("any market" in t.value for t in app.title)


# --- How it works --------------------------------------------------------------------------------

def test_how_it_works_has_the_flow_the_tools_and_the_data_sources(page):  # noqa: F811
    app = open_page(page(), "how")

    assert "How it works" in [t.value for t in app.title]
    assert "flowchart LR" in html(app)                                  # drawn by Mermaid
    shown = markdown(app)
    for tool in ("create_market_report", "web_search", "search_news", "read_webpage",
                 "get_demand_trend", "get_company_financials", "save_report", "remember_preference"):
        assert tool in shown, tool
    assert "Where the data comes from" in [h.value for h in app.subheader]
    assert len(app.chat_input) == 0                                     # no question box here


def test_how_it_works_follows_the_language(page):  # noqa: F811
    app = open_page(page(), "how")

    switch(app).set_value("de").run()

    assert "So funktioniert es" in [t.value for t in app.title]
    assert "Woher die Daten kommen" in [h.value for h in app.subheader]
    assert "Ihre Frage" in html(app)                                   # the chart's words too
