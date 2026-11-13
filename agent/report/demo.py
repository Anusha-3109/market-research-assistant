"""Run the report workflow from the terminal and print each step.

    python -m agent.report.demo "healthy meal delivery" Germany
"""

import operator
import sys

from agent.config import MissingKeyError, check_keys
from agent.report.graph import build_report_graph

# Fields that parallel branches add to, so their updates must be joined.
LIST_FIELDS = {"verified", "rejected", "profiles", "log"}


def run(product: str, country: str) -> dict:
    """Run the workflow, printing progress, and return the final state."""
    graph = build_report_graph()
    final: dict = {}

    # stream_mode="updates" yields each step's result as soon as it is done.
    for update in graph.stream({"product": product, "country": country},
                               stream_mode="updates"):
        for step, result in update.items():
            for line in (result or {}).get("log", []):
                print(f"[{step}] {line}")
            for field, value in (result or {}).items():
                if field in LIST_FIELDS:
                    final[field] = operator.add(final.get(field, []), value)
                else:
                    final[field] = value
    return final


def show(final: dict) -> None:
    order = [c.name for c in final.get("competitors", [])]
    profiles = sorted(final.get("profiles", []), key=lambda p: order.index(p.name))

    print("\n=== Competitors ===")
    for profile in profiles:
        print(f"\n{profile.name}  ({profile.shop_url or 'shop not found'})")
        figures = [line for line in profile.figures.splitlines()
                   if line.startswith(("Revenue", "Employees", "Founded", "Source"))]
        print("  figures: " + ("; ".join(figures) if figures else "not found"))
        if profile.prices:
            print(f"  prices from {profile.price_source}:")
            for price in profile.prices:
                print(f"    - {price.product}: {price.price}")
        else:
            print(f"  prices: not found ({profile.price_note})")

    print("\n=== Market figures ===")
    for figure in final.get("market_figures", []):
        print(f"- [{figure.scope}] {figure.statement}: {figure.value} "
              f"({figure.area}, {figure.year}) {figure.source_url}")

    print("\n=== News ===")
    for item in final.get("news", []):
        print(f"- {item.date}: {item.summary} {item.source_url}")

    print("\n=== Demand trend ===")
    trend = final.get("trend")
    if trend:
        print(f"term: {trend.term} | reliable: {trend.reliable}")
        print(trend.summary)
    else:
        print("not found")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 3:
        print('Usage: python -m agent.report.demo "<product>" <country>')
        return
    try:
        check_keys()
    except MissingKeyError as error:
        print(f"Setup problem: {error}")
        return

    final = run(sys.argv[1], sys.argv[2])
    if "--facts" in sys.argv:
        show(final)
    print()
    print(final.get("report", "No report was produced."))


if __name__ == "__main__":
    main()
