"""Tracing with LangSmith (https://smith.langchain.com).

With tracing on, every run is sent to LangSmith as a trace: each call to
the model, each tool call and each step of the report workflow, with how
long it took, what it cost and any error. It answers "why did the agent do
that?" after the fact.

LangChain traces by itself once a few settings are in the environment.
This file puts them in place:

- Tracing is on only when a key is set. Without one it is switched off, so
  nothing tries to send traces and warns about a missing key.
- A copy on your own computer and the deployed copy trace to two projects,
  so experiments and real visitors' runs are not mixed.
- LANGSMITH_TRACING=false switches it off with the key still in place.

A trace holds what people typed and what was answered. It is labelled with
the account's internal id only, never with a name or an email address.
"""

import os

LOCAL_PROJECT = "markavi-local"
LIVE_PROJECT = "markavi-live"


def configure_tracing(env=None) -> bool:
    """Put the tracing settings in place. Returns True if tracing is on.

    env is the environment to change; os.environ unless a test passes its
    own.
    """
    env = os.environ if env is None else env
    has_key = bool(env.get("LANGSMITH_API_KEY", "").strip())
    wanted = env.get("LANGSMITH_TRACING", "true").strip().lower() != "false"
    if not (has_key and wanted):
        env["LANGSMITH_TRACING"] = "false"
        return False
    env["LANGSMITH_TRACING"] = "true"
    if not env.get("LANGSMITH_PROJECT", "").strip():
        # Cloud Run sets K_SERVICE in every container it starts.
        env["LANGSMITH_PROJECT"] = LIVE_PROJECT if env.get("K_SERVICE") else LOCAL_PROJECT
    return True


def tracing_is_on(env=None) -> bool:
    env = os.environ if env is None else env
    return (env.get("LANGSMITH_TRACING", "").strip().lower() == "true"
            and bool(env.get("LANGSMITH_API_KEY", "").strip()))


def trace_labels(name: str, tag: str, thread_id: str | None = None, context=None) -> dict:
    """The part of a run's config that names and labels its trace.

    thread_id: LangSmith groups the runs of one conversation by it.
    context:   the UserContext; its account id, model and language are
               added so traces can be filtered by them.
    """
    metadata = {}
    if thread_id:
        metadata["thread_id"] = thread_id
    for label, field in (("user_id", "user_id"), ("model", "model_name"), ("language", "language")):
        value = getattr(context, field, None)
        if value:
            metadata[label] = value
    return {"run_name": name, "tags": [tag], "metadata": metadata}
