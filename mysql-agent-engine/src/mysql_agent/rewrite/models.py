"""Data models for SQL rewrite."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RewriteFinding:
    rule_id: str
    rule_name: str
    message: str
    rewritten_sql: str
    explanation: str = ""
    expected_benefit: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "message": self.message,
            "rewritten_sql": self.rewritten_sql,
            "explanation": self.explanation,
            "expected_benefit": self.expected_benefit,
        }


@dataclass
class RewriteResult:
    sql: str
    rewritten_sql: str
    primary_rule_id: str
    findings: List[RewriteFinding] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "sql": self.sql,
            "rewritten_sql": self.rewritten_sql,
            "primary_rule_id": self.primary_rule_id,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
        }
