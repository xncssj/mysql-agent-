"""Tests for L5 baseline regression comparison."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mysql_agent.eval.compare_baseline import (
    BaselineRegressionError,
    build_baseline_snapshot,
    compare_against_baseline,
    detect_scope,
    load_baseline,
)
from mysql_agent.eval.run_all import enrich_report

BASELINE_PATH = (
    Path(__file__).resolve().parents[2]
    / "eval/baseline.json"
)


@pytest.fixture
def baseline() -> dict:
    return load_baseline(BASELINE_PATH)


def _report(total: int, passed: int, l1_total: int, l1_passed: int, l2_total: int, l2_passed: int) -> dict:
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "layers": {
            "l1": {
                "total": l1_total,
                "passed": l1_passed,
                "pass_rate": round(l1_passed / l1_total, 4) if l1_total else 0.0,
            },
            "l2": {
                "total": l2_total,
                "passed": l2_passed,
                "pass_rate": round(l2_passed / l2_total, 4) if l2_total else 0.0,
            },
        },
        "results": [],
    }


def test_baseline_file_matches_golden_set_size(baseline: dict):
    assert baseline["total"] == baseline["passed"]
    assert baseline["pass_rate"] == 1.0
    assert baseline["layers"]["l1"]["total"] == baseline["layers"]["l1"]["passed"]
    assert baseline["layers"]["l2"]["total"] == baseline["layers"]["l2"]["passed"]
    assert baseline["total"] == baseline["layers"]["l1"]["total"] + baseline["layers"]["l2"]["total"]


def test_compare_full_scope_passes(baseline: dict):
    total = baseline["total"]
    l1 = baseline["layers"]["l1"]["total"]
    l2 = baseline["layers"]["l2"]["total"]
    report = _report(total, total, l1, l1, l2, l2)
    summary = compare_against_baseline(report, baseline)
    assert summary["passed"] is True
    assert summary["scope"] == "full"
    assert detect_scope(report, baseline) == "full"


def test_compare_l1_scope_passes_without_rag(baseline: dict):
    l1 = baseline["layers"]["l1"]["total"]
    report = _report(l1, l1, l1, l1, 0, 0)
    summary = compare_against_baseline(report, baseline)
    assert summary["passed"] is True
    assert summary["scope"] == "l1"


def test_compare_regression_fails_when_l1_drops(baseline: dict):
    l1 = baseline["layers"]["l1"]["total"]
    # Drop enough cases to exceed default 5% regression budget.
    dropped = max(int(l1 * 0.1), 3)
    report = _report(l1, max(l1 - dropped, 0), l1, max(l1 - dropped, 0), 0, 0)
    with pytest.raises(BaselineRegressionError):
        compare_against_baseline(report, baseline, max_regression=0.05)


def test_build_baseline_snapshot_from_enriched_report():
    raw = {
        "golden_set": "eval/golden_set.jsonl",
        "total": 2,
        "passed": 2,
        "pass_rate": 1.0,
        "results": [
            {"id": "EX001", "task": "explain_diagnosis", "passed": True, "message": "ok"},
            {"id": "RAG001", "task": "rag_retrieval", "passed": True, "message": "ok"},
        ],
    }
    enriched = enrich_report(raw)
    snapshot = build_baseline_snapshot(enriched)
    assert snapshot["task_breakdown"]["explain_diagnosis"]["passed"] == 1
    assert snapshot["layers"]["l2"]["total"] == 1


def test_baseline_json_is_valid():
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert data["version"] == "1.0"
