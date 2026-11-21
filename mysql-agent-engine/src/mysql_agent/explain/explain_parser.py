"""Parse MySQL EXPLAIN output into structured plans.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Union

from .models import ExplainPlan, ExplainRow

KNOWN_EXTRA_PATTERNS = [
    "Using index",
    "Using where",
    "Using filesort",
    "Using temporary",
    "Using index condition",
    "Using join buffer",
    "Impossible WHERE",
    "Select tables optimized away",
    "Backward index scan",
    "Using index merge",
]


def parse_extra(extra_str: str) -> List[str]:
    if not extra_str:
        return []

    extras: List[str] = []
    for pattern in KNOWN_EXTRA_PATTERNS:
        if pattern.lower() in extra_str.lower():
            extras.append(pattern)
    return extras or [extra_str.strip()]


def _infer_table(sql: str) -> str:
    match = re.search(r"\bFROM\s+([`\"\w]+)", sql, re.IGNORECASE)
    if match:
        return match.group(1).strip("`\"")
    return "unknown"


def _normalize_possible_keys(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _row_from_mapping(data: Dict[str, Any], sql: str, default_id: int = 1) -> ExplainRow:
    extra_raw = data.get("Extra") or data.get("extra") or ""
    if isinstance(extra_raw, list):
        extra = extra_raw
    else:
        extra = parse_extra(str(extra_raw))

    return ExplainRow(
        id=int(data.get("id", default_id)),
        select_type=str(data.get("select_type", "SIMPLE")),
        table=str(data.get("table") or _infer_table(sql)),
        partitions=data.get("partitions"),
        access_type=str(data.get("type") or data.get("access_type") or "ALL"),
        possible_keys=_normalize_possible_keys(data.get("possible_keys")),
        key=data.get("key"),
        key_len=int(data["key_len"]) if data.get("key_len") not in (None, "") else None,
        ref=data.get("ref"),
        rows=int(data.get("rows") or data.get("rows_examined_per_scan") or 0),
        filtered=float(data["filtered"]) if data.get("filtered") not in (None, "") else None,
        extra=extra,
    )


class ExplainParser:
    """Parse EXPLAIN output from JSON, tabular text, or simplified dicts."""

    def parse(self, explain_output: Union[str, Dict[str, Any], List[Dict[str, Any]]], sql: str = "") -> ExplainPlan:
        if isinstance(explain_output, list):
            rows = [_row_from_mapping(item, sql, idx + 1) for idx, item in enumerate(explain_output)]
            return ExplainPlan(sql=sql, rows=rows)

        if isinstance(explain_output, dict):
            if "query_block" in explain_output:
                return self._parse_json(explain_output, sql)
            return ExplainPlan(sql=sql, rows=[_row_from_mapping(explain_output, sql)])

        if isinstance(explain_output, str):
            try:
                data = json.loads(explain_output)
            except json.JSONDecodeError:
                return self._parse_tabular(explain_output, sql)
            if isinstance(data, list):
                rows = [_row_from_mapping(item, sql, idx + 1) for idx, item in enumerate(data)]
                return ExplainPlan(sql=sql, rows=rows)
            return self._parse_json(data, sql)

        raise TypeError(f"Unsupported explain output type: {type(explain_output)}")

    def _parse_json(self, data: Dict[str, Any], sql: str) -> ExplainPlan:
        rows: List[ExplainRow] = []
        query_block = data.get("query_block", {})
        tables = query_block.get("table", [])
        if isinstance(tables, dict):
            tables = [tables]

        for idx, table_data in enumerate(tables, start=1):
            rows.append(
                ExplainRow(
                    id=table_data.get("id", idx),
                    select_type=table_data.get("select_type", "SIMPLE"),
                    table=table_data.get("table_name", _infer_table(sql)),
                    partitions=table_data.get("partitions"),
                    access_type=table_data.get("access_type", "ALL"),
                    possible_keys=_normalize_possible_keys(table_data.get("possible_keys")),
                    key=table_data.get("key"),
                    key_len=table_data.get("key_length"),
                    ref=table_data.get("ref"),
                    rows=int(table_data.get("rows_examined_per_scan", 0)),
                    filtered=table_data.get("filtered"),
                    extra=self._parse_extra_json(table_data),
                )
            )

        return ExplainPlan(sql=sql, rows=rows)

    def _parse_tabular(self, output: str, sql: str) -> ExplainPlan:
        lines = output.strip().split("\n")
        rows: List[ExplainRow] = []

        for line in lines[1:]:
            if not line.strip() or line.startswith("+"):
                continue

            parts = [part.strip() for part in line.split("|")][1:-1]
            if len(parts) < 10:
                continue

            rows.append(
                ExplainRow(
                    id=int(parts[0]) if parts[0].isdigit() else 1,
                    select_type=parts[1],
                    table=parts[2],
                    partitions=parts[3] or None,
                    access_type=parts[4],
                    possible_keys=_normalize_possible_keys(parts[5]),
                    key=parts[6] or None,
                    key_len=int(parts[7]) if parts[7].isdigit() else None,
                    ref=parts[8] or None,
                    rows=int(parts[9]) if parts[9].isdigit() else 0,
                    filtered=float(parts[10]) if len(parts) > 10 and parts[10] else None,
                    extra=parse_extra(parts[11] if len(parts) > 11 else ""),
                )
            )

        return ExplainPlan(sql=sql, rows=rows)

    def _parse_extra_json(self, table_data: Dict[str, Any]) -> List[str]:
        extras: List[str] = []
        if table_data.get("using_index"):
            extras.append("Using index")
        if table_data.get("using_where"):
            extras.append("Using where")
        if table_data.get("using_filesort"):
            extras.append("Using filesort")
        if table_data.get("using_temporary"):
            extras.append("Using temporary")
        if table_data.get("using_index_condition"):
            extras.append("Using index condition")
        return extras