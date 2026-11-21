"""Data models for index analysis."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class IndexRuleLevel(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class IndexColumn:
    name: str
    seq_in_index: int
    cardinality: Optional[int] = None
    sub_part: Optional[int] = None


@dataclass
class TableIndex:
    table: str
    index_name: str
    columns: List[IndexColumn]
    is_unique: bool = False
    index_type: str = "BTREE"


@dataclass
class TableSchema:
    database: str
    table: str
    columns: Dict[str, str] = field(default_factory=dict)
    indexes: List[TableIndex] = field(default_factory=list)
    row_count: int = 0
    avg_row_length: int = 0


@dataclass
class IndexFinding:
    rule_id: str
    rule_name: str
    level: str
    table: str
    message: str
    suggested_ddl: Optional[str] = None
    evidence: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "level": self.level,
            "table": self.table,
            "message": self.message,
            "suggested_ddl": self.suggested_ddl,
            "evidence": self.evidence,
        }
