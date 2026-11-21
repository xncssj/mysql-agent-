#!/usr/bin/env python3
"""CLI for EXPLAIN diagnosis."""
from __future__ import annotations

import argparse
import json

from mysql_agent.agents.explain_agent import ExplainDiagnosisAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose a MySQL EXPLAIN plan")
    parser.add_argument("--sql", required=True, help="SQL statement")
    parser.add_argument("--explain", required=True, help="EXPLAIN JSON string or path to JSON file")
    args = parser.parse_args()

    explain_input = args.explain
    if explain_input.endswith(".json"):
        explain_input = json.loads(open(explain_input, "r", encoding="utf-8").read())
    else:
        try:
            explain_input = json.loads(explain_input)
        except json.JSONDecodeError:
            pass

    agent = ExplainDiagnosisAgent()
    result = agent.diagnose(args.sql, explain_input)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
