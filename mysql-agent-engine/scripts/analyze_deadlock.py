#!/usr/bin/env python3
"""CLI for deadlock analysis."""
from __future__ import annotations

import argparse
import json

from mysql_agent.agents.deadlock_agent import DeadlockAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze InnoDB deadlock output")
    parser.add_argument("--file", required=True, help="Path to INNODB STATUS snippet")
    args = parser.parse_args()

    agent = DeadlockAgent()
    result = agent.analyze_file(args.file)
    if not result:
        print(json.dumps({"status": "no_deadlock"}, ensure_ascii=False, indent=2))
        return
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
