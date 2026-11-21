"""Risk analyzer for EXPLAIN plans.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from .models import ExplainPlan, ExplainRow, RiskLevel
from .risk_rules import RISK_PATTERNS, RiskPattern


@dataclass
class RiskFinding:
    rule_id: str
    rule_name: str
    level: str
    issue: str
    evidence: str
    suggestion: str
    table: str
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RiskAnalyzer:
    """Apply deterministic EXPLAIN rules to a parsed plan."""

    def __init__(self, knowledge_base: Optional[Any] = None):
        self.rules = RISK_PATTERNS
        self.kb = knowledge_base

    def analyze(self, plan: ExplainPlan) -> List[RiskFinding]:
        findings: List[RiskFinding] = []
        seen_rule_ids: set[str] = set()

        for row in plan.rows:
            for rule in self.rules:
                if rule.id in seen_rule_ids:
                    continue
                try:
                    if not rule.check(row, plan):
                        continue
                except Exception:
                    continue

                finding = self._build_finding(rule, row)
                findings.append(finding)
                seen_rule_ids.add(rule.id)

        level_order = {RiskLevel.CRITICAL.value: 0, RiskLevel.WARNING.value: 1, RiskLevel.INFO.value: 2}
        findings.sort(key=lambda item: (level_order.get(item.level, 3), item.rule_id))
        return findings

    def _build_finding(self, rule: RiskPattern, row: ExplainRow) -> RiskFinding:
        evidence = (
            f"type={row.access_type}, key={row.key or 'NULL'}, rows={row.rows}, "
            f"extra={', '.join(row.extra) if row.extra else 'N/A'}"
        )
        return RiskFinding(
            rule_id=rule.id,
            rule_name=rule.name,
            level=rule.level.value,
            issue=rule.description,
            evidence=evidence,
            suggestion=self._render_suggestion(rule, row),
            table=row.table,
            context={
                "access_type": row.access_type,
                "key": row.key,
                "rows": row.rows,
                "extra": row.extra,
            },
        )

    def _render_suggestion(self, rule: RiskPattern, row: ExplainRow) -> str:
        return rule.suggestion_template.format(
            table=row.table,
            rows=row.rows,
            key=row.key or "N/A",
            possible_keys=", ".join(row.possible_keys) if row.possible_keys else "N/A",
        )