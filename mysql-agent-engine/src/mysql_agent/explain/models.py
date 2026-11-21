"""Data models for MySQL EXPLAIN analysis.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ExplainRow:
    """Single row from an EXPLAIN plan."""

    id: int
    select_type: str
    table: str
    partitions: Optional[str]
    access_type: str
    possible_keys: List[str]
    key: Optional[str]
    key_len: Optional[int]
    ref: Optional[str]
    rows: int
    filtered: Optional[float]
    extra: List[str]

    @property
    def is_full_scan(self) -> bool:
        return self.access_type.upper() in ("ALL", "INDEX")

    @property
    def has_filesort(self) -> bool:
        return any("filesort" in item.lower() for item in self.extra)

    @property
    def has_temporary(self) -> bool:
        return any("temporary" in item.lower() for item in self.extra)

    @property
    def is_covering_index(self) -> bool:
        extras = " ".join(self.extra).lower()
        return "using index" in extras and "using where" not in extras


@dataclass
class ExplainPlan:
    """Complete EXPLAIN plan for a SQL statement."""

    sql: str
    rows: List[ExplainRow]
    warnings: List[str] = field(default_factory=list)

    @property
    def total_rows_examined(self) -> int:
        return sum(row.rows for row in self.rows)

    @property
    def has_full_scan(self) -> bool:
        return any(row.is_full_scan for row in self.rows)

    def get_table_plan(self, table_name: str) -> Optional[ExplainRow]:
        for row in self.rows:
            if row.table == table_name:
                return row
        return None