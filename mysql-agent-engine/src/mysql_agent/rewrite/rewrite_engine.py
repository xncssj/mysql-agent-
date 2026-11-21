"""SQL rewrite engine."""
from __future__ import annotations

from typing import List

from .models import RewriteFinding, RewriteResult
from .rewrite_rules import RULE_MAP, RULE_PRIORITY, REWRITE_RULES


class SQLRewriteEngine:
    """Apply deterministic SQL rewrite rules in priority order."""

    def __init__(self):
        self.rules = REWRITE_RULES
        self.priority = RULE_PRIORITY

    def detect(self, sql: str) -> List[str]:
        return [rule.rule_id for rule in self.rules if rule.matches(sql)]

    def rewrite(self, sql: str) -> RewriteResult:
        matched_findings: List[RewriteFinding] = []
        for rule_id in self.priority:
            rule = RULE_MAP[rule_id]
            if not rule.matches(sql):
                continue
            finding = rule.rewrite(sql)
            if finding:
                matched_findings.append(finding)

        if not matched_findings:
            return RewriteResult(
                sql=sql,
                rewritten_sql=sql,
                primary_rule_id="",
                findings=[],
                summary="未匹配到可应用的 SQL 改写规则。",
            )

        primary = matched_findings[0]
        return RewriteResult(
            sql=sql,
            rewritten_sql=primary.rewritten_sql,
            primary_rule_id=primary.rule_id,
            findings=matched_findings,
            summary=f"应用规则 {primary.rule_id}：{primary.rule_name}",
        )
