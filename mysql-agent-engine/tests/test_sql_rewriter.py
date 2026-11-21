import json
from pathlib import Path

import pytest

from mysql_agent.agents.sql_rewriter import SQLRewriterAgent
from mysql_agent.eval.run import evaluate_rewrite_case, load_golden_set, run_evaluation

GOLDEN_SET = (
    Path(__file__).resolve().parents[2]
    / "eval/golden_set.jsonl"
)


@pytest.fixture
def agent() -> SQLRewriterAgent:
    return SQLRewriterAgent()


def test_rewrite_golden_set_passes(agent: SQLRewriterAgent):
    cases = [case for case in load_golden_set(GOLDEN_SET) if case["task"] == "sql_rewrite"]
    results = [evaluate_rewrite_case(case, agent) for case in cases]
    failed = [result for result in results if not result.passed]
    assert not failed, json.dumps([result.__dict__ for result in failed], ensure_ascii=False, indent=2)


def test_rw001_in_subquery_to_join(agent: SQLRewriterAgent):
    result = agent.rewrite(
        "SELECT * FROM orders WHERE id IN (SELECT order_id FROM order_items WHERE product_id=100)"
    )
    assert result.primary_rule_id == "W001"
    assert "JOIN" in result.rewritten_sql.upper()


def test_rw002_year_function(agent: SQLRewriterAgent):
    result = agent.rewrite("SELECT * FROM orders WHERE YEAR(created_at)=2024")
    assert result.primary_rule_id == "W008"
    assert "created_at >=" in result.rewritten_sql


def test_rw003_large_offset(agent: SQLRewriterAgent):
    result = agent.rewrite("SELECT * FROM orders ORDER BY id LIMIT 100000, 20")
    assert result.primary_rule_id == "W005"


def test_run_evaluation_rewrite_only():
    report = run_evaluation(GOLDEN_SET, tasks=["sql_rewrite"])
    assert report["total"] == 3
    assert report["passed"] == 3
    assert report["pass_rate"] == 1.0
