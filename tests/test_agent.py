"""Tests for how the agent is put together, using fake models (no internet,
no API cost)."""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent.agent import assemble_agent


def answering(text: str) -> GenericFakeChatModel:
    """A fake model that replies with the given text."""
    return GenericFakeChatModel(messages=iter([AIMessage(text)]))


class DownModel(GenericFakeChatModel):
    """A fake model that always fails, like a provider outage."""

    def _generate(self, *args, **kwargs):
        raise ConnectionError("model provider is down")


def down() -> DownModel:
    return DownModel(messages=iter([]))


def ask(agent) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": "Hello"}]})
    return result["messages"][-1].content


def test_the_main_model_answers_when_it_is_working():
    agent = assemble_agent(answering("from main"), [answering("from backup")], tools=[])

    assert ask(agent) == "from main"


def test_the_backup_model_answers_when_the_main_model_is_down():
    agent = assemble_agent(down(), [answering("from backup")], tools=[])

    assert ask(agent) == "from backup"


def test_the_second_backup_answers_when_the_first_two_are_down():
    agent = assemble_agent(down(), [down(), answering("from second backup")], tools=[])

    assert ask(agent) == "from second backup"


def test_an_error_is_raised_when_every_model_is_down():
    agent = assemble_agent(down(), [down()], tools=[])

    with pytest.raises(ConnectionError):
        ask(agent)


def test_the_agent_works_without_any_backup_models():
    agent = assemble_agent(answering("only model"), [], tools=[])

    assert ask(agent) == "only model"
