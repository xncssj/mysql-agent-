#!/usr/bin/env python3
"""CLI for cross-correlation analysis."""
from __future__ import annotations

import argparse
import json

from mysql_agent.agents.cross_correlation_agent import CrossCorrelationAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze metric cross-correlation patterns")
    parser.add_argument("--metrics", required=True, help="JSON object of metric -> values[]")
    args = parser.parse_args()

    metrics = json.loads(args.metrics)
    agent = CrossCorrelationAgent()
    result = agent.analyze(metrics)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
