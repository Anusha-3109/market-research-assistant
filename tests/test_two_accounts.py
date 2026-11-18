"""Tests that two accounts on the same copy of the app do not see each
other's conversations or what is remembered about them.

The page is run without a browser. Anna and Ben are made-up people.
"""

from langchain_core.messages import AIMessage
from streamlit.testing.v1 import AppTest

from agent import accounts, memory, session
from agent.agent import stream_steps
from tests.test_app import button
from tests.test_sign_in import APP, PASSWORD, START_TITLE, create, sign_in, site  # noqa: F401
from tests.test_styles import ListeningModel

ANNA, BEN = "u-anna", "u-ben"


def two_accounts(site, replies=None, model=None):  # noqa: F811
    site.allow_agent(replies=replies, model=model)
    accounts.create_account(site.store, "anna", "Anna", PASSWORD, email="anna@example.com")
    accounts.create_account(site.store, "ben", "Ben", PASSWORD)
    # Nothing was there before the accounts, and that has been settled.
    session.adopt_existing(site.store, site.runtime.checkpointer, ANNA)


def visit_as(site, username: str, conversation: str | None = None):  # noqa: F811
    """Open the page in a new browser session and sign in. With a
    conversation id, the page is opened at that conversation's address."""
    app = AppTest.from_file(APP, default_timeout=30)
    if conversation:
        app.query_params["c"] = conversation
    return sign_in(app.run(), username, PASSWORD)


def ask(app, question: str):
    app.chat_input[0].set_value(question).run()
    return app


def address(app) -> str:
    """The id of the conversation in the page address."""
    value = app.query_params["c"]
    return value[0] if isinstance(value, list) else value


def listed(app) -> list[str]:
    """The conversations in the sidebar."""
    return [b.label for b in app.sidebar.button if (b.key or "").startswith("open_")]


def on_page(app) -> str:
    return "\n".join(element.value for element in
                     list(app.markdown) + list(app.caption) + list(app.subheader))


# --- conversations -----------------------------------------------------------------------------

def test_a_conversation_is_listed_only_for_the_account_that_started_it(site):  # noqa: F811
    two_accounts(site, replies=[AIMessage("An answer for Anna.")])
    ask(visit_as(site, "anna"), "Anna's question about oat milk")

    assert listed(visit_as(site, "ben")) == []
    assert listed(visit_as(site, "anna")) == ["Anna's question about oat milk"]


def test_the_address_of_another_accounts_conversation_opens_an_empty_one(site):  # noqa: F811
    two_accounts(site, replies=[AIMessage("An answer for Anna.")])
    annas = address(ask(visit_as(site, "anna"), "Anna's question about oat milk"))

    ben = visit_as(site, "ben", conversation=annas)

    assert not ben.exception
    assert ben.title[0].value == START_TITLE
    assert address(ben) != annas
    assert "An answer for Anna." not in on_page(ben)
    assert "oat milk" not in on_page(ben)


def test_your_own_conversation_opens_again_from_its_address(site):  # noqa: F811
    two_accounts(site, replies=[AIMessage("An answer for Anna.")])
    annas = address(ask(visit_as(site, "anna"), "Anna's question about oat milk"))

    again = visit_as(site, "anna", conversation=annas)

    assert address(again) == annas
    assert "An answer for Anna." in on_page(again)


def test_a_question_cannot_be_added_to_another_accounts_conversation(site):  # noqa: F811
    two_accounts(site, replies=[AIMessage("An answer for Anna."), AIMessage("An answer for Ben.")])
    annas = address(ask(visit_as(site, "anna"), "Anna's question about oat milk"))

    ben = ask(visit_as(site, "ben", conversation=annas), "Ben's question")

    assert session.owner_of(site.store, address(ben)) == BEN
    assert len(session.load_messages(site.runtime.agent, annas)) == 2     # Anna's question and answer


# --- what is remembered --------------------------------------------------------------------------

def test_what_is_remembered_about_one_account_is_not_shown_to_another(site):  # noqa: F811
    two_accounts(site)
    memory.save_preference(site.store, ANNA, "region", "Portugal")

    assert any("Portugal" in m.value for m in visit_as(site, "anna").sidebar.markdown)
    assert not any("Portugal" in m.value for m in visit_as(site, "ben").sidebar.markdown)


def test_forget_me_clears_only_your_own_account(site):  # noqa: F811
    two_accounts(site)
    memory.save_preference(site.store, ANNA, "region", "Portugal")
    memory.save_preference(site.store, BEN, "region", "Norway")

    button(visit_as(site, "ben").sidebar, "forget_me").click().run()

    assert memory.load_profile(site.store, BEN) == {}
    assert memory.load_profile(site.store, ANNA) == {"region": "Portugal"}


def test_the_agent_is_told_only_what_is_remembered_about_the_account_asking(site):  # noqa: F811
    model = ListeningModel(messages=iter([AIMessage("ok"), AIMessage("ok")]))
    two_accounts(site, model=model)
    memory.save_preference(site.store, ANNA, "region", "Portugal")
    memory.save_preference(site.store, BEN, "region", "Norway")

    ask(visit_as(site, "anna"), "How big is the oat milk market?")
    told_for_anna = model.told()
    ask(visit_as(site, "ben"), "How big is the oat milk market?")
    told_for_ben = model.told()

    assert "Portugal" in told_for_anna and "Norway" not in told_for_anna
    assert "Norway" in told_for_ben and "Portugal" not in told_for_ben


# --- what was there before there were accounts ----------------------------------------------------

def test_the_first_account_created_takes_over_the_old_conversations_and_memory(site):  # noqa: F811
    site.allow_agent(replies=[AIMessage("An old answer.")])
    list(stream_steps(site.runtime.agent, "A question from before accounts", "old-thread"))
    memory.save_preference(site.store, memory.DEFAULT_USER, "region", "Portugal")

    first = create(site.visit(), name="Anna", username="anna")
    second = create(site.visit(), name="Ben", username="ben", email="ben@example.com")

    assert listed(first) == ["A question from before accounts"]
    assert any("Portugal" in m.value for m in first.sidebar.markdown)
    assert listed(second) == []
    assert not any("Portugal" in m.value for m in second.sidebar.markdown)
