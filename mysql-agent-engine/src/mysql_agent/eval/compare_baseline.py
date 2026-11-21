"""Compare evaluation reports against a frozen L5 baseline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class BaselineRegressionError(Exception):
    """Raised when pass rate drops beyond the allowed regression threshold."""


def load_baseline(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _metric_for_scope(
    report: Dict[str, Any],
    baseline: Dict[str, Any],
    scope: str,
) -> tuple[str, float, float]:
    layers = report.get("layers", {})
    baseline_layers = baseline.get("layers", {})

    if scope == "full":
        return "pass_rate", float(report["pass_rate"]), float(baseline["pass_rate"])
    if scope == "l1":
        return (
            "layers.l1.pass_rate",
            float(layers["l1"]["pass_rate"]),
            float(baseline_layers["l1"]["pass_rate"]),
        )
    raise ValueError(f"unsupported scope: {scope}")


def detect_scope(report: Dict[str, Any], baseline: Dict[str, Any]) -> str:
    if report["total"] == baseline["total"]:
        return "full"
    layers = report.get("layers", {})
    baseline_layers = baseline.get("layers", {})
    if layers.get("l1", {}).get("total") == baseline_layers.get("l1", {}).get("total"):
        return "l1"
    raise ValueError(
        "report case count does not match baseline full or L1 scope: "
        f"report={report['total']} baseline={baseline['total']}"
    )


def compare_against_baseline(
    report: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    max_regression: float = 0.05,
    scope: Optional[str] = None,
) -> Dict[str, Any]:
    """Return comparison summary; raises BaselineRegressionError on failure."""
    resolved_scope = scope or detect_scope(report, baseline)
    metric_name, current, expected = _metric_for_scope(report, baseline, resolved_scope)
    regression = round(expected - current, 4)
    passed = regression <= max_regression

    failed_cases = [
        {"id": item["id"], "task": item["task"], "message": item["message"]}
        for item in report.get("results", [])
        if not item["passed"]
    ]

    summary = {
        "scope": resolved_scope,
        "metric": metric_name,
        "baseline": expected,
        "current": current,
        "regression": regression,
        "max_regression": max_regression,
        "passed": passed,
        "failed_cases": failed_cases,
    }
    if not passed:
        raise BaselineRegressionError(
            f"L5 regression: {metric_name} dropped {regression:.2%} "
            f"(baseline={expected:.2%}, current={current:.2%}, limit={max_regression:.2%})"
        )
    return summary


def build_baseline_snapshot(report: Dict[str, Any], *, note: str = "") -> Dict[str, Any]:
    from datetime import date

    return {
        "version": "1.0",
        "created_at": date.today().isoformat(),
        "note": note,
        "golden_set": report.get("golden_set"),
        "total": report["total"],
        "passed": report["passed"],
        "pass_rate": report["pass_rate"],
        "layers": report.get("layers", {}),
        "task_breakdown": report.get("task_breakdown", {}),
    }


def write_baseline(path: str | Path, snapshot: Dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
