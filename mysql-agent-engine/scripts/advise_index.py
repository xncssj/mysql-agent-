#!/usr/bin/env python3
"""CLI for index advice."""
from __future__ import annotations

import argparse
import json

from mysql_agent.agents.index_agent import IndexAdvisorAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend indexes for a SQL statement")
    parser.add_argument("--sql", required=True, help="SQL statement")
    parser.add_argument("--table", required=True, help="Target table name")
    parser.add_argument("--explain", help="Optional EXPLAIN JSON string")
    args = parser.parse_args()

    explain_input = None
    if args.explain:
        explain_input = json.loads(args.explain)

    agent = IndexAdvisorAgent()
    result = agent.advise(args.sql, table=args.table, explain=explain_input)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
