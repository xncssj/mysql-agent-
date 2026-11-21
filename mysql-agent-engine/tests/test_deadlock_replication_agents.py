import json
from pathlib import Path

import pytest

from mysql_agent.agents.deadlock_agent import DeadlockAgent
from mysql_agent.agents.replication_agent import ReplicationAgent
from mysql_agent.eval.run import (
    evaluate_deadlock_case,
    evaluate_replication_case,
    load_golden_set,
    run_evaluation,
)

GOLDEN_SET = (
    Path(__file__).resolve().parents[2]
    / "eval/golden_set.jsonl"
)
DEADLOCK_FIXTURE = GOLDEN_SET.parent / "fixtures/deadlock_001.txt"


@pytest.fixture
def deadlock_agent() -> DeadlockAgent:
    return DeadlockAgent()


@pytest.fixture
def replication_agent() -> ReplicationAgent:
    return ReplicationAgent()


def test_deadlock_fixture_parse(deadlock_agent: DeadlockAgent):
    result = deadlock_agent.analyze_file(DEADLOCK_FIXTURE)
    assert result is not None
    assert result.deadlock_type == "lock_order"
    assert result.victim == 2


def test_deadlock_golden_set_passes(deadlock_agent: DeadlockAgent):
    cases = [case for case in load_golden_set(GOLDEN_SET) if case["task"] == "deadlock_parse"]
    results = [evaluate_deadlock_case(case, deadlock_agent, GOLDEN_SET) for case in cases]
    failed = [result for result in results if not result.passed]
    assert not failed, json.dumps([result.__dict__ for result in failed], ensure_ascii=False, indent=2)


def test_replication_golden_set_passes(replication_agent: ReplicationAgent):
    cases = [case for case in load_golden_set(GOLDEN_SET) if case["task"] == "replication"]
    results = [evaluate_replication_case(case, replication_agent) for case in cases]
    failed = [result for result in results if not result.passed]
    assert not failed, json.dumps([result.__dict__ for result in failed], ensure_ascii=False, indent=2)


def test_rp001_io_thread_stopped(replication_agent: ReplicationAgent):
    result = replication_agent.diagnose(
        {"Slave_IO_Running": "No", "Last_IO_Error": "error connecting to master"}
    )
    rule_ids = {finding.rule_id for finding in result.findings}
    assert "RP01" in rule_ids
    assert result.findings[0].level == "CRITICAL"


def test_run_evaluation_deadlock_and_replication():
    report = run_evaluation(GOLDEN_SET, tasks=["deadlock_parse", "replication"])
    assert report["total"] == 5
    assert report["passed"] == 5
    assert report["pass_rate"] == 1.0
