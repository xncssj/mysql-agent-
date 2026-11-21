#!/usr/bin/env python3
"""CLI for MySQL ReAct orchestrator (default entry)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mysql_agent.llm import HeuristicLLMClient, OpenAILLMClient
from mysql_agent.metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector
from mysql_agent.orchestrator import AgentBundle, ReActOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MySQL ReAct orchestrator")
    parser.add_argument("--query", required=True)
    parser.add_argument("--context", help="JSON context with sql/anomalies/metrics/etc")
    parser.add_argument("--index-path", help="Vector index path for RAG")
    parser.add_argument("--metrics-fixture", help="JSON fixture for Prometheus collector")
    parser.add_argument("--prometheus-url", help="Prometheus base URL")
    parser.add_argument("--llm", choices=["heuristic", "openai"], default="heuristic")
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()

    metrics_agent = None
    if args.metrics_fixture:
        fixture_data = json.loads(Path(args.metrics_fixture).read_text(encoding="utf-8"))
        collector = PrometheusCollector(fixture_data=fixture_data)
        metrics_agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))
    elif args.prometheus_url:
        collector = PrometheusCollector(prometheus_url=args.prometheus_url)
        metrics_agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))

    llm = OpenAILLMClient(model=args.model) if args.llm == "openai" else HeuristicLLMClient()
    bundle = AgentBundle.create_default(
        index_path=args.index_path,
        metrics_agent=metrics_agent,
        prometheus_url=args.prometheus_url if not args.metrics_fixture else None,
        llm_client=llm if args.llm == "openai" else None,
    )
    orchestrator = ReActOrchestrator(bundle, llm_client=llm)
    context = json.loads(args.context) if args.context else {}
    if context.get("innodb_status_file"):
        context["innodb_status_file"] = str(Path(context["innodb_status_file"]).expanduser())
    result = orchestrator.run(args.query, context=context)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
