"""L3 Prompt / Agent output JSON Schema validation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "eval/schemas"
COLUMN_SCHEMA_DIR = (
    Path(__file__).resolve().parents[4]
    / "eval/schemas"
)


def _resolve_schema(name: str) -> Path:
    for base in (SCHEMA_DIR, COLUMN_SCHEMA_DIR):
        path = base / name
        if path.exists():
            return path
    raise FileNotFoundError(f"schema not found: {name} (looked in {SCHEMA_DIR}, {COLUMN_SCHEMA_DIR})")


def load_schema(name: str) -> Dict[str, Any]:
    return json.loads(_resolve_schema(name).read_text(encoding="utf-8"))


def validate_payload(data: Dict[str, Any], schema_name: str) -> Tuple[bool, str]:
    try:
        import jsonschema
    except ImportError as exc:
        raise SystemExit("jsonschema is required: pip install 'mysql-agent-engine[dev]'") from exc

    schema = load_schema(schema_name)
    try:
        jsonschema.validate(data, schema)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001 — surface validator message
        return False, str(exc)


def collect_rule_path_samples() -> List[Dict[str, Any]]:
    """Offline samples that mimic agent JSON outputs (no OpenAI required)."""
    from ..agents.nl2sql_agent import NL2SQLAgent
    from ..reporting import ReportGenerator

    samples: List[Dict[str, Any]] = []
    report = ReportGenerator().generate(
        {
            "anomalies": [
                {
                    "metric": "connections_pct",
                    "severity": "CRITICAL",
                    "description": "连接数过高",
                    "timestamp": "2026-01-01T00:00:00",
                }
            ],
            "root_causes": [
                {
                    "root_cause_id": "RC02",
                    "name": "锁等待/死锁",
                    "score": 0.9,
                    "evidence": ["connections_pct=CRITICAL"],
                }
            ],
            "summary": {"critical": 1, "warning": 0},
        },
        instance_id="mysql-prod-01",
    )
    markdown = getattr(report, "markdown", "") or str(report)
    samples.append(
        {
            "id": "RPT_SCHEMA",
            "schema": "report.json",
            "payload": {
                "summary": markdown[:200],
                "root_cause": "RC02",
                "suggestions": ["检查长事务", "统一加锁顺序"],
            },
        }
    )

    nl = NL2SQLAgent()
    result = nl.generate("查询慢查询 TOP10")
    sql = getattr(result, "sql", "") or "SELECT 1"
    samples.append(
        {
            "id": "NL_SCHEMA",
            "schema": "nl2sql.json",
            "payload": {"sql": sql, "description": "slow query top10"},
        }
    )
    return samples


def run_validation(samples: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    samples = samples or collect_rule_path_samples()
    results = []
    for item in samples:
        ok, message = validate_payload(item["payload"], item["schema"])
        results.append({"id": item["id"], "schema": item["schema"], "passed": ok, "message": message})
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "compliance_rate": round(passed / total, 4) if total else 0.0,
        "results": results,
    }


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="L3 schema compliance check")
    parser.add_argument("--min-compliance", type=float, default=0.98)
    args = parser.parse_args(argv)
    report = run_validation()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["compliance_rate"] >= args.min_compliance else 1)


if __name__ == "__main__":
    main()
