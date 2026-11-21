#!/usr/bin/env python3
"""Scan MySQL instance metrics from Prometheus."""
from __future__ import annotations

import argparse
import json

from mysql_agent.metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan MySQL metrics via Prometheus")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--duration-minutes", type=int, default=60)
    parser.add_argument("--fixture", help="JSON fixture file for offline testing")
    args = parser.parse_args()

    fixture_data = None
    if args.fixture:
        fixture_data = json.loads(open(args.fixture, encoding="utf-8").read())

    collector = PrometheusCollector(
        prometheus_url=args.prometheus_url,
        fixture_data=fixture_data,
    )
    agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))
    result = agent.run(duration_minutes=args.duration_minutes)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
