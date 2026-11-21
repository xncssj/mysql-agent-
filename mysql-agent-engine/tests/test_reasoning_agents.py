import json
from pathlib import Path

import pytest

from mysql_agent.agents.cross_correlation_agent import CrossCorrelationAgent
from mysql_agent.agents.root_cause_agent import RootCauseAgent
from mysql_agent.eval.run import (
    evaluate_cross_correlation_case,
    evaluate_root_cause_case,
    load_golden_set,
    run_evaluation,
)

GOLDEN_SET = (
    Path(__file__).resolve().parents[2]
    / "eval/golden_set.jsonl"
)


@pytest.fixture
def root_cause_agent() -> RootCauseAgent:
    return RootCauseAgent()


@pytest.fixture
def cross_agent() -> CrossCorrelationAgent:
    return CrossCorrelationAgent()


def test_root_cause_golden_set_passes(root_cause_agent: RootCauseAgent):
    cases = [case for case in load_golden_set(GOLDEN_SET) if case["task"] == "root_cause"]
    results = [evaluate_root_cause_case(case, root_cause_agent) for case in cases]
    failed = [result for result in results if not result.passed]
    assert not failed, json.dumps([result.__dict__ for result in failed], ensure_ascii=False, indent=2)


def test_cross_correlation_golden_set_passes(cross_agent: CrossCorrelationAgent):
    cases = [case for case in load_golden_set(GOLDEN_SET) if case["task"] == "cross_correlation"]
    results = [evaluate_cross_correlation_case(case, cross_agent) for case in cases]
    failed = [result for result in results if not result.passed]
    assert not failed, json.dumps([result.__dict__ for result in failed], ensure_ascii=False, indent=2)


def test_rc001_lock_and_slow_query(root_cause_agent: RootCauseAgent):
    result = root_cause_agent.diagnose(
        [
            {"metric": "slow_query_rate", "severity": "CRITICAL"},
            {"metric": "row_lock_time_avg", "severity": "WARNING"},
        ]
    )
    assert result.top_root_cause == "RC02"
    assert result.cross_pattern == "CC06"


def test_cc001_connections_and_locks(cross_agent: CrossCorrelationAgent):
    result = cross_agent.analyze(
        {
            "connections_pct": [50, 60, 75, 85, 91],
            "row_lock_time_avg": [50, 200, 500, 1200, 2300],
        }
    )
    assert result.top_pattern_id == "CC01"
    assert result.top_root_cause == "RC02"


def test_run_evaluation_instance_path():
    from mysql_agent.eval.run import load_golden_set

    expected = len(
        [c for c in load_golden_set(GOLDEN_SET) if c["task"] in {"root_cause", "cross_correlation"}]
    )
    report = run_evaluation(GOLDEN_SET, tasks=["root_cause", "cross_correlation"])
    assert report["total"] == expected
    assert report["passed"] == expected
    assert report["pass_rate"] == 1.0
