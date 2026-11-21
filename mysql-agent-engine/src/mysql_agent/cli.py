#!/usr/bin/env python3
"""Unified CLI for mysql-agent-engine.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mysql_agent.agents.deadlock_agent import DeadlockAgent
from mysql_agent.agents.explain_agent import ExplainDiagnosisAgent
from mysql_agent.agents.index_agent import IndexAdvisorAgent
from mysql_agent.agents.nl2sql_agent import NL2SQLAgent
from mysql_agent.agents.rag_agent import MySQLRAGAgent
from mysql_agent.agents.replication_agent import ReplicationAgent
from mysql_agent.agents.root_cause_agent import RootCauseAgent
from mysql_agent.agents.sql_rewriter import SQLRewriterAgent
from mysql_agent.eval.run import run_evaluation
from mysql_agent.llm import HeuristicLLMClient, OpenAILLMClient
from mysql_agent.metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector
from mysql_agent.orchestrator import AgentBundle, MySQLOrchestrator, ReActOrchestrator


def _build_llm(args: argparse.Namespace):
    if args.llm == "openai":
        return OpenAILLMClient(model=args.model)
    return HeuristicLLMClient()


def _build_bundle(args: argparse.Namespace) -> AgentBundle:
    metrics_agent = None
    if args.metrics_fixture:
        fixture = json.loads(Path(args.metrics_fixture).read_text(encoding="utf-8"))
        collector = PrometheusCollector(fixture_data=fixture)
        metrics_agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))
    elif args.prometheus_url:
        collector = PrometheusCollector(prometheus_url=args.prometheus_url)
        metrics_agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))

    llm = _build_llm(args) if args.llm == "openai" else None
    return AgentBundle.create_default(
        index_path=args.index_path,
        metrics_agent=metrics_agent,
        prometheus_url=args.prometheus_url if not args.metrics_fixture else None,
        schema_path=args.schema_path,
        llm_client=llm,
    )


def cmd_explain(args: argparse.Namespace) -> None:
    agent = ExplainDiagnosisAgent()
    explain = json.loads(args.explain) if args.explain else {"type": "ALL", "rows": 1_000_000}
    result = agent.diagnose(args.sql, explain)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_index(args: argparse.Namespace) -> None:
    agent = IndexAdvisorAgent()
    explain = json.loads(args.explain) if args.explain else {"type": "ALL", "rows": 1_000_000}
    result = agent.advise(args.sql, args.table, explain)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_rewrite(args: argparse.Namespace) -> None:
    agent = SQLRewriterAgent()
    result = agent.rewrite(args.sql)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_metrics(args: argparse.Namespace) -> None:
    if args.metrics_fixture:
        fixture = json.loads(Path(args.metrics_fixture).read_text(encoding="utf-8"))
        collector = PrometheusCollector(fixture_data=fixture)
    else:
        collector = PrometheusCollector(prometheus_url=args.prometheus_url)
    agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))
    print(json.dumps(agent.run(args.duration_minutes), ensure_ascii=False, indent=2))


def cmd_nl2sql(args: argparse.Namespace) -> None:
    agent = NL2SQLAgent(schema_path=args.schema_path)
    print(json.dumps(agent.generate(args.question).to_dict(), ensure_ascii=False, indent=2))


def cmd_deadlock(args: argparse.Namespace) -> None:
    agent = DeadlockAgent()
    status = Path(args.innodb_status_file).read_text(encoding="utf-8")
    result = agent.analyze(status)
    print(json.dumps(result.to_dict() if result else {"status": "no_deadlock"}, ensure_ascii=False, indent=2))


def cmd_replication(args: argparse.Namespace) -> None:
    agent = ReplicationAgent()
    slave_status = json.loads(args.slave_status) if args.slave_status else {}
    print(json.dumps(agent.diagnose(slave_status).to_dict(), ensure_ascii=False, indent=2))


def cmd_rag(args: argparse.Namespace) -> None:
    agent = MySQLRAGAgent(args.index_path, quiet=True)
    if args.question:
        print(json.dumps(agent.query(args.question).__dict__, ensure_ascii=False, indent=2))
    else:
        agent.interactive()


def cmd_chat(args: argparse.Namespace) -> None:
    bundle = _build_bundle(args)
    llm = _build_llm(args)
    orchestrator = ReActOrchestrator(bundle, llm_client=llm)
    context = json.loads(args.context) if args.context else {}
    result = orchestrator.run(args.query, context=context)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_orchestrate(args: argparse.Namespace) -> None:
    bundle = _build_bundle(args)
    orchestrator = MySQLOrchestrator(bundle)
    context = json.loads(args.context) if args.context else {}
    result = orchestrator.run(args.query, context=context)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def cmd_eval(args: argparse.Namespace) -> None:
    report = run_evaluation(args.golden_set, index_path=args.index_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="MySQL Agent CLI")
    parser.add_argument("--index-path", help="Vector index path for RAG")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--metrics-fixture")
    parser.add_argument("--schema-path")
    parser.add_argument("--llm", choices=["heuristic", "openai"], default="heuristic")
    parser.add_argument("--model", default="gpt-4o-mini")
    sub = parser.add_subparsers(dest="command", required=True)

    explain = sub.add_parser("explain", help="Analyze SQL EXPLAIN output")
    explain.add_argument("--sql", required=True)
    explain.add_argument("--explain")
    explain.set_defaults(func=cmd_explain)

    index = sub.add_parser("index", help="Index advice")
    index.add_argument("--sql", required=True)
    index.add_argument("--table", required=True)
    index.add_argument("--explain")
    index.set_defaults(func=cmd_index)

    rewrite = sub.add_parser("rewrite", help="Rewrite SQL")
    rewrite.add_argument("--sql", required=True)
    rewrite.set_defaults(func=cmd_rewrite)

    metrics = sub.add_parser("metrics", help="Scan Prometheus metrics")
    metrics.add_argument("--duration-minutes", type=int, default=60)
    metrics.set_defaults(func=cmd_metrics)

    nl2sql = sub.add_parser("nl2sql", help="Generate SQL from natural language")
    nl2sql.add_argument("--question", required=True)
    nl2sql.set_defaults(func=cmd_nl2sql)

    deadlock = sub.add_parser("deadlock", help="Analyze deadlock")
    deadlock.add_argument("--innodb-status-file", required=True)
    deadlock.set_defaults(func=cmd_deadlock)

    replication = sub.add_parser("replication", help="Diagnose replication")
    replication.add_argument("--slave-status")
    replication.set_defaults(func=cmd_replication)

    rag = sub.add_parser("rag", help="Knowledge base Q&A")
    rag.add_argument("--question")
    rag.set_defaults(func=cmd_rag)

    chat = sub.add_parser("chat", help="ReAct orchestrator")
    chat.add_argument("--query", required=True)
    chat.add_argument("--context")
    chat.set_defaults(func=cmd_chat)

    orchestrate = sub.add_parser("orchestrate", help="Rule-based orchestrator")
    orchestrate.add_argument("--query", required=True)
    orchestrate.add_argument("--context")
    orchestrate.set_defaults(func=cmd_orchestrate)

    eval_cmd = sub.add_parser("eval", help="Run golden set evaluation")
    eval_cmd.add_argument("--golden-set", required=True)
    eval_cmd.set_defaults(func=cmd_eval)

    args = parser.parse_args()
    if args.command == "rag" and not args.index_path:
        parser.error("rag requires --index-path")
    if args.command == "eval" and not args.golden_set:
        parser.error("eval requires --golden-set")
    args.func(args)


if __name__ == "__main__":
    main()