"""Layered evaluation entrypoint with optional L5 baseline regression check."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compare_baseline import (
    BaselineRegressionError,
    build_baseline_snapshot,
    compare_against_baseline,
    load_baseline,
    write_baseline,
)
from .layers import summarize_layers, task_breakdown
from .run import run_evaluation

DEFAULT_GOLDEN_SET = Path(__file__).resolve().parents[3] / "eval/golden_set.jsonl"
COLUMN_GOLDEN_SET = (
    Path(__file__).resolve().parents[4]
    / "eval/golden_set.jsonl"
)
if not DEFAULT_GOLDEN_SET.exists() and COLUMN_GOLDEN_SET.exists():
    DEFAULT_GOLDEN_SET = COLUMN_GOLDEN_SET
DEFAULT_BASELINE = DEFAULT_GOLDEN_SET.parent / "baseline.json"
DEFAULT_INDEX = Path(__file__).resolve().parents[3] / "data/ci_vector_index"
COLUMN_INDEX = (
    Path(__file__).resolve().parents[4]
    / "data/vector_index"
)
if not DEFAULT_INDEX.exists() and COLUMN_INDEX.exists():
    DEFAULT_INDEX = COLUMN_INDEX
L2_TASKS = {"rag_retrieval"}


def enrich_report(report: dict) -> dict:
    results = report.get("results", [])
    report["layers"] = summarize_layers(results)
    report["task_breakdown"] = task_breakdown(results)
    return report


def resolve_index_path(
    index_path: str | None,
    skip_rag_without_index: bool,
) -> tuple[str | None, list[str] | None]:
    """Return (index_path, exclude_tasks). exclude_tasks lists L2 tasks to skip."""
    if index_path:
        path = Path(index_path)
        if not path.exists():
            if skip_rag_without_index:
                print(f"⚠️  Index not found at {path}; running L1-only (skipping rag_retrieval)", file=sys.stderr)
                return None, sorted(L2_TASKS)
            raise FileNotFoundError(f"vector index not found: {path}")
        return str(path), None

    if DEFAULT_INDEX.exists():
        return str(DEFAULT_INDEX), None

    if skip_rag_without_index:
        print(
            f"⚠️  Vector index missing at {DEFAULT_INDEX}; running L1-only (skipping rag_retrieval)",
            file=sys.stderr,
        )
        return None, sorted(L2_TASKS)

    return None, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all MySQL Agent evaluations")
    parser.add_argument("--golden-set", default=str(DEFAULT_GOLDEN_SET))
    parser.add_argument("--index-path", help="Vector index path for RAG cases")
    parser.add_argument(
        "--skip-rag-without-index",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip rag_retrieval when index is unavailable (default: true)",
    )
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="L5 baseline JSON path")
    parser.add_argument("--max-regression", type=float, default=0.05, help="Max allowed pass_rate drop")
    parser.add_argument("--report", help="Write full JSON report to this path")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite baseline.json from the current run (release only)",
    )
    parser.add_argument(
        "--no-baseline-check",
        action="store_true",
        help="Run evaluation without comparing to baseline",
    )
    args = parser.parse_args()

    index_path, exclude_tasks = resolve_index_path(args.index_path, args.skip_rag_without_index)
    report = run_evaluation(
        args.golden_set,
        index_path=index_path,
        exclude_tasks=exclude_tasks,
    )
    report = enrich_report(report)

    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    output = {
        "evaluation": {
            "total": report["total"],
            "passed": report["passed"],
            "pass_rate": report["pass_rate"],
            "layers": report["layers"],
        }
    }

    if args.update_baseline:
        snapshot = build_baseline_snapshot(report, note="Updated via run_all --update-baseline")
        write_baseline(args.baseline, snapshot)
        output["baseline_updated"] = args.baseline
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    if not args.no_baseline_check:
        baseline = load_baseline(args.baseline)
        try:
            output["regression"] = compare_against_baseline(
                report,
                baseline,
                max_regression=args.max_regression,
            )
        except BaselineRegressionError as exc:
            output["regression"] = {
                "passed": False,
                "error": str(exc),
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            raise SystemExit(1) from exc

    print(json.dumps(output, ensure_ascii=False, indent=2))
    if report.get("pass_rate", 0) < 1.0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
