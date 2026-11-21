#!/usr/bin/env python3
"""CLI for replication diagnosis."""
from __future__ import annotations

import argparse
import json

from mysql_agent.agents.replication_agent import ReplicationAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose MySQL replication status")
    parser.add_argument("--slave-status", required=True, help="JSON object of SHOW SLAVE STATUS fields")
    args = parser.parse_args()

    agent = ReplicationAgent()
    result = agent.diagnose(json.loads(args.slave_status))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
