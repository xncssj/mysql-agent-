"""Auto-score L4 E2E cases via tool-coverage heuristic (1-5)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..orchestrator import AgentBundle, ReActOrchestrator
from ..metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector
from ..reporting import ReportGenerator


def load_cases(path: Path) -> List[Dict[str, Any]]:
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def score_tools(expected: List[str], actual: List[str]) -> float:
    if not expected:
        return 5.0
    hit = sum(1 for t in expected if t in actual)
    ratio = hit / len(expected)
    # map 0..1 -> 1..5
    return round(1 + ratio * 4, 2)


def run_case(case: Dict[str, Any], bundle: AgentBundle, cases_dir: Path) -> Dict[str, Any]:
    context = dict(case.get("context") or {})
    if context.get("metrics_file"):
        # prefer engine fixtures
        for candidate in (
            Path("tests/fixtures/metrics.json"),
            cases_dir / "fixtures" / "metrics.json",
            Path(context["metrics_file"]),
        ):
            if candidate.exists():
                fixture = json.loads(candidate.read_text(encoding="utf-8"))
                collector = PrometheusCollector(fixture_data=fixture)
                bundle.metrics = MetricsAnalysisAgent(
                    collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS)
                )
                break
    if context.get("metrics_fixture_file"):
        p = cases_dir / context["metrics_fixture_file"]
        if p.exists():
            fixture = json.loads(p.read_text(encoding="utf-8"))
            collector = PrometheusCollector(fixture_data=fixture)
            bundle.metrics = MetricsAnalysisAgent(
                collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS)
            )
    if context.get("innodb_status_file"):
        p = Path(context["innodb_status_file"])
        if not p.exists():
            p = cases_dir / context["innodb_status_file"]
        if p.exists():
            context["innodb_status_file"] = str(p)

    orch = ReActOrchestrator(bundle)
    result = orch.run(case["user_query"], context=context)
    tools = [step.tool for step in result.steps]
    auto = score_tools(case.get("expected_tools") or [], tools)
    return {
        **case,
        "auto_score": auto,
        "human_score": case.get("human_score"),
        "reviewer": case.get("reviewer") or "auto_v1",
        "actual_tools": tools,
        "answer_preview": (result.answer or "")[:240],
        "notes": case.get("notes") or "",
    }


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Auto-score E2E cases")
    parser.add_argument(
        "--cases",
        default=str(Path(__file__).resolve().parents[3] / "eval/e2e_manual_cases.jsonl"),
    )
    parser.add_argument("--index-path", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default="")
    parser.add_argument("--min-avg", type=float, default=4.0)
    args = parser.parse_args(argv)

    cases_path = Path(args.cases)
    cases = load_cases(cases_path)
    if args.limit:
        cases = cases[: args.limit]

    index_path = args.index_path or None
    if index_path and not Path(index_path).exists():
        index_path = None

    bundle = AgentBundle.create_default(index_path=index_path)
    bundle.report = ReportGenerator()

    scored = [run_case(case, bundle, cases_path.parent) for case in cases]
    avg = sum(c["auto_score"] for c in scored) / len(scored) if scored else 0.0
    report = {
        "total": len(scored),
        "avg_auto_score": round(avg, 3),
        "passed_avg_ge_min": avg >= args.min_avg,
        "min_avg": args.min_avg,
        "gte4": sum(1 for c in scored if c["auto_score"] >= 4),
        "cases": scored,
    }

    out = Path(args.out) if args.out else cases_path.with_name("e2e_auto_scores.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # rewrite jsonl with auto_score filled
    lines = []
    for c in scored:
        slim = {
            "case_id": c["case_id"],
            "user_query": c["user_query"],
            "context": c.get("context") or {},
            "expected_tools": c.get("expected_tools") or [],
            "human_score": c.get("human_score"),
            "auto_score": c.get("auto_score"),
            "reviewer": c.get("reviewer"),
            "notes": c.get("notes"),
            "actual_tools": c.get("actual_tools"),
        }
        lines.append(json.dumps(slim, ensure_ascii=False))
    cases_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({k: report[k] for k in ("total", "avg_auto_score", "passed_avg_ge_min", "gte4", "min_avg")}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed_avg_ge_min"] else 1)


if __name__ == "__main__":
    main()
