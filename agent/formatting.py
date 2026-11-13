"""Small helpers for turning numbers into readable text."""


def format_money(value, currency: str) -> str:
    """Format a large number as, for example, '7.6 billion EUR'."""
    if not isinstance(value, (int, float)):
        return "not found"
    for size, name in ((1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
        if abs(value) >= size:
            return f"{value / size:.1f} {name} {currency}".strip()
    return f"{value:,.0f} {currency}".strip()
