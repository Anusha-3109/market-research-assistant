"""Try several data sources in order until one answers.

This is what keeps the app working when a service is down. A tool gives
try_sources a list of sources, most preferred first. The first one that
returns something useful wins; the others are not called.
"""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as SourceTimeout
from dataclasses import dataclass, field
from typing import Any, Callable

from agent.config import SOURCE_TIMEOUT_SECONDS

# A source is a display name and a function, for example
# ("Tavily", tavily.search).
Source = tuple[str, Callable[..., Any]]


@dataclass
class FallbackResult:
    """What happened when a list of sources was tried."""

    value: Any = None             # the winning source's result, or None
    used: str | None = None       # name of the source that answered
    failures: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)

    @property
    def succeeded(self) -> bool:
        return self.used is not None

    def source_note(self) -> str:
        """One line saying where the data came from, for the model to read.

        Examples:
            Source used: Tavily
            Source used: DuckDuckGo (Tavily unavailable)
            All sources unavailable: Tavily (timed out), DuckDuckGo (no results)
        """
        if not self.succeeded:
            tried = ", ".join(f"{name} ({reason})" for name, reason in self.failures)
            return f"All sources unavailable: {tried or 'none configured'}"
        if self.failures:
            failed = ", ".join(name for name, _ in self.failures)
            return f"Source used: {self.used} ({failed} unavailable)"
        return f"Source used: {self.used}"


def _call_with_timeout(function: Callable, args: tuple, timeout: float) -> Any:
    """Run a function, giving up after `timeout` seconds.

    The call runs in a worker thread so a hung service cannot freeze the
    app. Python cannot stop a running thread, so after a timeout the call is
    abandoned and left to finish in the background.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return executor.submit(function, *args).result(timeout=timeout)
    finally:
        executor.shutdown(wait=False)


def try_sources(
    sources: list[Source],
    *args: Any,
    timeout: float = SOURCE_TIMEOUT_SECONDS,
) -> FallbackResult:
    """Call each source in order with `args` and return the first useful
    result.

    A source counts as failed when it raises an error, takes longer than
    `timeout` seconds, or returns nothing (None, an empty list, an empty
    string). Any kind of error is caught, so a bug in one backup cannot
    stop the next one from being tried.
    """
    result = FallbackResult()

    for name, function in sources:
        try:
            value = _call_with_timeout(function, args, timeout)
        except SourceTimeout:
            result.failures.append((name, f"timed out after {timeout:g}s"))
            continue
        except Exception as error:
            result.failures.append((name, str(error) or type(error).__name__))
            continue

        if not value:
            result.failures.append((name, "no results"))
            continue

        result.value = value
        result.used = name
        return result

    return result
