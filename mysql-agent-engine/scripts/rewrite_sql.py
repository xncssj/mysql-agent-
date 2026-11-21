#!/usr/bin/env python3
"""CLI for SQL rewrite."""
from __future__ import annotations

import argparse
import json

from mysql_agent.agents.sql_rewriter import SQLRewriterAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Rewrite SQL using deterministic rules")
    parser.add_argument("--sql", required=True, help="SQL statement")
    args = parser.parse_args()

    agent = SQLRewriterAgent()
    result = agent.rewrite(args.sql)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
