"""Outside services the agent gets its data from.

Each file in this folder talks to exactly one service and knows nothing
about the agent. The rules every source follows:

- Search-style sources return a list of results. Each result is a dict with
  "title", "url", "content" and, for news, "published_date".
- A source raises SourceError when the service fails. It never returns an
  error as text; deciding what to tell the model is the tool's job.
"""


class SourceError(Exception):
    """A data source failed: network problem, bad key, rate limit or bad data."""
