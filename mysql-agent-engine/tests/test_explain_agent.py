import json
from pathlib import Path

import pytest

from mysql_agent.agents.explain_agent import ExplainDiagnosisAgent
from mysql_agent.eval.run import evaluate_explain_case, load_golden_set, run_evaluation

GOLDEN_SET = (
    Path(__file__).resolve().parents[2]
    / "eval/golden_set.jsonl"
)


@pytest.fixture
def agent() -> ExplainDiagnosisAgent:
    return ExplainDiagnosisAgent()


def test_explain_golden_set_passes(agent: ExplainDiagnosisAgent):
  cases = [case for case in load_golden_set(GOLDEN_SET) if case["task"] == "explain_diagnosis"]
  results = [evaluate_explain_case(case, agent) for case in cases]
  failed = [result for result in results if not result.passed]
  assert not failed, json.dumps([result.__dict__ for result in failed], ensure_ascii=False, indent=2)


def test_ex001_full_table_scan(agent: ExplainDiagnosisAgent):
  result = agent.diagnose(
      "SELECT * FROM orders WHERE status=1",
      {"type": "ALL", "rows": 5_000_000, "key": None, "Extra": "Using where"},
  )
  rule_ids = {finding.rule_id for finding in result.findings}
  assert "R001" in rule_ids
  assert result.findings[0].level == "CRITICAL"


def test_ex004_const_table(agent: ExplainDiagnosisAgent):
  result = agent.diagnose("SELECT * FROM t WHERE id=1", {"type": "const", "rows": 1})
  rule_ids = {finding.rule_id for finding in result.findings}
  assert "R010" in rule_ids


def test_run_evaluation_explain_only():
  report = run_evaluation(GOLDEN_SET, tasks=["explain_diagnosis"])
  assert report["total"] == 5
  assert report["passed"] == 5
  assert report["pass_rate"] == 1.0
