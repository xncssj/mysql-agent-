import json
from pathlib import Path

import pytest

from mysql_agent.eval.run import load_golden_set, run_evaluation
from mysql_agent.orchestrator import AgentBundle, InputRouter, MySQLOrchestrator

GOLDEN_SET = (
    Path(__file__).resolve().parents[2]
    / "eval/golden_set.jsonl"
)
INDEX_PATH = GOLDEN_SET.parent.parent / "data/vector_index"
DEADLOCK_FIXTURE = GOLDEN_SET.parent / "fixtures/deadlock_001.txt"


@pytest.fixture
def router() -> InputRouter:
    return InputRouter()


@pytest.fixture
def orchestrator() -> MySQLOrchestrator:
    return MySQLOrchestrator(AgentBundle.create_default())


def test_router_sql_layer(router: InputRouter):
    route = router.classify("SELECT * FROM orders WHERE status=1 怎么优化")
    assert route["layer"] == "sql"


def test_router_instance_layer(router: InputRouter):
    route = router.classify("数据库响应慢，连接数也很高")
    assert route["layer"] == "instance"


def test_router_deadlock_layer(router: InputRouter):
    route = router.classify("出现死锁了，帮我分析")
    assert route["layer"] == "advanced"
    assert "deadlock" in route["suggested_agents"]


def test_orchestrator_sql_pipeline(orchestrator: MySQLOrchestrator):
    result = orchestrator.run(
        "这条 SQL 很慢",
        context={
            "sql": "SELECT * FROM orders WHERE status=1 ORDER BY created_at DESC",
            "table": "orders",
        },
    )
    tools = {step.tool for step in result.steps}
    assert "explain_sql" in tools
    assert "suggest_index" in tools


def test_orchestrator_instance_pipeline(orchestrator: MySQLOrchestrator):
    result = orchestrator.run(
        "数据库慢了",
        context={
            "anomalies": [
                {"metric": "connections_pct", "severity": "CRITICAL"},
                {"metric": "row_lock_time_avg", "severity": "CRITICAL"},
            ]
        },
    )
    assert any(step.tool == "diagnose_root_cause" for step in result.steps)
    assert "RC02" in result.answer or any(
        step.result.get("top_root_cause") == "RC02" for step in result.steps
    )


def test_orchestrator_deadlock_pipeline(orchestrator: MySQLOrchestrator):
    result = orchestrator.run(
        "分析死锁",
        context={"innodb_status_file": str(DEADLOCK_FIXTURE)},
    )
    assert any(step.tool == "analyze_deadlock" for step in result.steps)
    deadlock_step = next(step for step in result.steps if step.tool == "analyze_deadlock")
    assert deadlock_step.result.get("type") == "lock_order"


@pytest.mark.skipif(
    not (INDEX_PATH / "faiss_index.bin").exists(), reason="vector index not built"
)
def test_full_golden_set_passes():
    from mysql_agent.eval.run import load_golden_set

    expected = len(load_golden_set(GOLDEN_SET))
    report = run_evaluation(GOLDEN_SET, index_path=str(INDEX_PATH))
    assert report["total"] == expected
    assert report["passed"] == expected
    assert report["pass_rate"] == 1.0
