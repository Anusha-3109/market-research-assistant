"""Run the report workflow from the terminal and print each step.

    python -m agent.report.demo "healthy meal delivery" Germany
"""

import sys

from agent.config import MissingKeyError, check_keys
from agent.report.graph import build_report_graph


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

    graph = build_report_graph()
    request = {"product": sys.argv[1], "country": sys.argv[2]}

    # stream_mode="updates" yields each step's result as soon as it is done.
    final = {}
    for update in graph.stream(request, stream_mode="updates"):
        for step, result in update.items():
            for line in (result or {}).get("log", []):
                print(f"[{step}] {line}")
            final.update(result or {})

    print("\nCompetitors for the report:")
    for competitor in final.get("competitors", []):
        print(f"- {competitor.name}")
        print(f"    shop:     {competitor.shop_url or 'not found'}")
        print(f"    evidence: {competitor.evidence_url}")
        print(f"    why:      {competitor.reason}")


if __name__ == "__main__":
    main()
