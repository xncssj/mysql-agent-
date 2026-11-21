"""Layer breakdown helpers for L1/L2 evaluation reports."""
from __future__ import annotations

from typing import Any, Dict, List

L1_TASKS = frozenset(
    {
        "explain_diagnosis",
        "index_advice",
        "sql_rewrite",
        "root_cause",
        "cross_correlation",
        "deadlock_parse",
        "replication",
        "nl2sql",
        "report_generation",
        "metrics_scan",
        "orchestrator_e2e",
    }
)
L2_TASKS = frozenset({"rag_retrieval"})


def summarize_layers(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, float | int]]:
    l1_passed = sum(1 for item in results if item["task"] in L1_TASKS and item["passed"])
    l1_total = sum(1 for item in results if item["task"] in L1_TASKS)
    l2_passed = sum(1 for item in results if item["task"] in L2_TASKS and item["passed"])
    l2_total = sum(1 for item in results if item["task"] in L2_TASKS)
    return {
        "l1": {
            "passed": l1_passed,
            "total": l1_total,
            "pass_rate": round(l1_passed / l1_total, 4) if l1_total else 0.0,
        },
        "l2": {
            "passed": l2_passed,
            "total": l2_total,
            "pass_rate": round(l2_passed / l2_total, 4) if l2_total else 0.0,
        },
    }


def task_breakdown(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    breakdown: Dict[str, Dict[str, int]] = {}
    for item in results:
        task = item["task"]
        stats = breakdown.setdefault(task, {"passed": 0, "total": 0})
        stats["total"] += 1
        if item["passed"]:
            stats["passed"] += 1
    return breakdown
