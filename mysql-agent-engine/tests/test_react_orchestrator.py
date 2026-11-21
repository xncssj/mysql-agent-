"""Tests for ReAct orchestrator."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mysql_agent.metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector
from mysql_agent.orchestrator import AgentBundle, ReActOrchestrator
from mysql_agent.reporting import ReportGenerator

GOLDEN_SET = (
    Path(__file__).resolve().parents[2]
    / "eval/golden_set.jsonl"
)
DEADLOCK_FIXTURE = GOLDEN_SET.parent / "fixtures/deadlock_001.txt"


def _fixture_metrics_agent() -> MetricsAnalysisAgent:
    start = datetime(2026, 1, 1, 0, 0, 0)
    series = [
        {"timestamp": start + timedelta(minutes=idx * 5), "value": 70 + idx * 2}
        for idx in range(10)
    ]
    collector = PrometheusCollector(
        fixture_data={
            "connections": series,
            "max_connections": [{"timestamp": point["timestamp"], "value": 100} for point in series],
            "slow_query_rate": [{"timestamp": point["timestamp"], "value": 0.002} for point in series],
        }
    )
    return MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))


@pytest.fixture
def react_orchestrator() -> ReActOrchestrator:
    bundle = AgentBundle.create_default(metrics_agent=_fixture_metrics_agent())
    bundle.report = ReportGenerator()
    return ReActOrchestrator(bundle)


def test_react_sql_pipeline(react_orchestrator: ReActOrchestrator):
    result = react_orchestrator.run(
        "这条 SQL 很慢，怎么优化",
        context={
            "sql": "SELECT * FROM orders WHERE status=1 ORDER BY created_at DESC",
            "table": "orders",
        },
    )
    tools = {step.tool for step in result.steps}
    assert "explain_sql" in tools
    assert "suggest_index" in tools
    assert result.answer


def test_react_instance_pipeline(react_orchestrator: ReActOrchestrator):
    result = react_orchestrator.run("数据库响应慢，连接数也很高")
    tools = [step.tool for step in result.steps]
    assert tools[0] == "check_instance_metrics"
    assert "diagnose_root_cause" in tools
    assert "generate_report" in tools


def test_react_deadlock_pipeline(react_orchestrator: ReActOrchestrator):
    result = react_orchestrator.run(
        "分析死锁",
        context={"innodb_status_file": str(DEADLOCK_FIXTURE)},
    )
    assert any(step.tool == "analyze_deadlock" for step in result.steps)
    deadlock_step = next(step for step in result.steps if step.tool == "analyze_deadlock")
    assert deadlock_step.result.get("type") == "lock_order"
