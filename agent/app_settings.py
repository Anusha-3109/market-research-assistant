"""The settings of the whole app, set on the Admin page.

The model, temperature, answer length, answer style and competitor review
apply to every account, and so do the system prompt and the tools the
agent may use. They are kept once, in the long-term store under
("app",) "settings". The language stays a choice of each account.
"""

from agent.memory import SETTING_DEFAULTS, clean_settings

NAMESPACE = ("app",)
KEY = "settings"
# The settings of agent/memory.py that the Admin page sets for everyone.
SHARED = [name for name in SETTING_DEFAULTS if name != "language"]


def tool_names() -> list[str]:
    from agent.agent import ALL_TOOLS      # here, because agent.agent imports this file
    return [tool.name for tool in ALL_TOOLS]


def load_app_settings(store) -> dict:
    """The app's settings, or the defaults. A value that is not one of the
    choices the app offers falls back to its default."""
    item = store.get(NAMESPACE, KEY) if store is not None else None
    saved = dict(item.value) if item else {}
    settings = {name: value for name, value in clean_settings(saved).items() if name in SHARED}
    prompt = saved.get("prompt", "")
    settings["prompt"] = prompt if isinstance(prompt, str) else ""
    known = set(tool_names())
    settings["disabled_tools"] = [name for name in saved.get("disabled_tools", [])
                                  if isinstance(name, str) and name in known]
    return settings


def save_app_settings(store, values: dict) -> None:
    """Save the app's settings; what is not given keeps its saved value."""
    settings = {**load_app_settings(store), **values}
    store.put(NAMESPACE, KEY, settings)


def custom_prompt(store) -> str:
    """The system prompt set on the Admin page, with today's date filled in,
    or "" when the built-in prompt is used."""
    from datetime import date

    prompt = load_app_settings(store)["prompt"].strip() if store is not None else ""
    return prompt.replace("{today}", date.today().isoformat())
