"""Describe a series of numbers over time as rising, falling or stable.

The arithmetic is done here, in code, and not left to the language model:
models are unreliable at averaging dozens of numbers, and the result has to
be the same every time.
"""

from dataclasses import dataclass
from statistics import median

# A change smaller than this, in either direction, counts as stable.
STABLE_BAND_PERCENT = 15


@dataclass
class TrendSeries:
    """Interest in something over time, from one source."""

    label: str                       # what was measured, and where
    unit: str                        # what the numbers mean
    points: list[tuple[str, float]]  # (date, value), oldest first
    url: str                         # where a person can check it
    note: str = ""                   # any limitation of this source
    # Set only for a 0-100 index: a typical (median) value below this means
    # there were too few searches for the trend to be trusted.
    low_volume_below: float | None = None


def average(values: list[float]) -> float:
    return sum(values) / len(values)


def is_low_volume(series: TrendSeries) -> bool:
    """True when a 0-100 index is built on too few searches to be trusted.

    The median is used, not the average: one unusually busy week can lift
    the average of an otherwise empty chart above the threshold.
    """
    if series.low_volume_below is None:
        return False
    return median(value for _, value in series.points) < series.low_volume_below


def summarise(series: TrendSeries) -> str:
    """Compare the first quarter of the period with the last quarter and
    return a short description with the figures behind it."""
    values = [value for _, value in series.points]
    quarter = max(1, len(values) // 4)
    start = average(values[:quarter])
    end = average(values[-quarter:])
    peak_date, peak_value = max(series.points, key=lambda point: point[1])

    if start == 0:
        direction = "rising from almost nothing" if end > 0 else "no measurable interest"
        change = "percentage change cannot be calculated from a zero start"
    else:
        percent = (end - start) / start * 100
        if percent > STABLE_BAND_PERCENT:
            direction = "rising"
        elif percent < -STABLE_BAND_PERCENT:
            direction = "falling"
        else:
            direction = "stable"
        change = f"{percent:+.0f}% from the first to the last quarter of the period"

    lines = [
        series.label,
        f"Period: {series.points[0][0]} to {series.points[-1][0]} "
        f"({len(values)} data points)",
        f"Direction: {direction} ({change})",
        f"Average at the start: {start:,.0f} | at the end: {end:,.0f} | "
        f"peak: {peak_value:,.0f} on {peak_date}",
        f"Unit: {series.unit}",
        f"Source: {series.url}",
    ]
    if is_low_volume(series):
        lines.append(
            "Reliability: low. There are very few searches for this term, so "
            "the direction may be noise. Say this when you report the trend, "
            "or try a more common term."
        )
    if series.note:
        lines.append(f"Note: {series.note}")
    return "\n".join(lines)
