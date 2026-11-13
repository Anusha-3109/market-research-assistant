"""One shared way to make web requests, used by the keyless sources."""

import requests

from agent.config import SOURCE_TIMEOUT_SECONDS
from agent.sources import SourceError

# Public services ask automated clients to identify themselves.
HEADERS = {"User-Agent": "market-research-assistant/0.1 (educational project)"}


def get(url: str, params: dict | None = None) -> requests.Response:
    """Fetch a URL and return the response, or raise SourceError.

    A non-success status such as 429 (rate limited) or 503 (service down)
    counts as a failure.
    """
    try:
        response = requests.get(
            url, params=params, headers=HEADERS, timeout=SOURCE_TIMEOUT_SECONDS
        )
    except requests.RequestException as error:
        raise SourceError(str(error)) from error

    if not response.ok:
        raise SourceError(f"HTTP {response.status_code} from {url}")
    return response
