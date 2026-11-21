#!/usr/bin/env python3
"""CLI for root cause diagnosis."""
from __future__ import annotations

import argparse
import json

from mysql_agent.agents.root_cause_agent import RootCauseAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose instance root causes from anomalies")
    parser.add_argument("--anomalies", required=True, help="JSON array of {metric, severity}")
    args = parser.parse_args()

    anomalies = json.loads(args.anomalies)
    agent = RootCauseAgent()
    result = agent.diagnose(anomalies)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
