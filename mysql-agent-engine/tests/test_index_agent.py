import json
from pathlib import Path

import pytest

from mysql_agent.agents.index_agent import IndexAdvisorAgent
from mysql_agent.eval.run import evaluate_index_case, load_golden_set, run_evaluation

GOLDEN_SET = (
    Path(__file__).resolve().parents[2]
    / "eval/golden_set.jsonl"
)


@pytest.fixture
def agent() -> IndexAdvisorAgent:
    return IndexAdvisorAgent()


def test_index_golden_set_passes(agent: IndexAdvisorAgent):
    cases = [case for case in load_golden_set(GOLDEN_SET) if case["task"] == "index_advice"]
    results = [evaluate_index_case(case, agent) for case in cases]
    failed = [result for result in results if not result.passed]
    assert not failed, json.dumps([result.__dict__ for result in failed], ensure_ascii=False, indent=2)


def test_idx001_missing_equality_index(agent: IndexAdvisorAgent):
    result = agent.advise(
        "SELECT * FROM orders WHERE status=1 ORDER BY created_at DESC",
        table="orders",
    )
    rule_ids = {finding.rule_id for finding in result.findings}
    ddl = " ".join(result.ddl_suggestions).lower()
    assert "I001" in rule_ids
    assert "status" in ddl
    assert "created_at" in ddl


def test_idx002_missing_join_index(agent: IndexAdvisorAgent):
    result = agent.advise(
        "SELECT * FROM orders o JOIN users u ON o.user_id=u.id WHERE o.status=2",
        table="orders",
    )
    rule_ids = {finding.rule_id for finding in result.findings}
    ddl = " ".join(result.ddl_suggestions).lower()
    assert "I003" in rule_ids
    assert "user_id" in ddl


def test_idx003_covering_index(agent: IndexAdvisorAgent):
    result = agent.advise(
        "SELECT order_id, total_amount FROM orders WHERE status=1",
        table="orders",
        explain={"type": "ref", "Extra": "Using index"},
    )
    rule_ids = {finding.rule_id for finding in result.findings}
    assert "I011" in rule_ids


def test_run_evaluation_index_only():
    report = run_evaluation(GOLDEN_SET, tasks=["index_advice"])
    assert report["total"] == 3
    assert report["passed"] == 3
    assert report["pass_rate"] == 1.0
