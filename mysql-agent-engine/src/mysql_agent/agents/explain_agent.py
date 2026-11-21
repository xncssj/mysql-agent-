"""Explain diagnosis agent.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..explain import ExplainParser, RiskAnalyzer, RiskFinding


@dataclass
class ExplainDiagnosisResult:
    sql: str
    findings: List[RiskFinding] = field(default_factory=list)
    summary: str = ""
    optimization_sql: str = ""
    ddl_suggestions: List[str] = field(default_factory=list)
    plan_overview: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sql": self.sql,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
            "optimization_sql": self.optimization_sql,
            "ddl_suggestions": self.ddl_suggestions,
            "plan_overview": self.plan_overview,
        }


class ExplainDiagnosisAgent:
    """Rule-driven EXPLAIN diagnosis agent."""

    def __init__(self, knowledge_base: Optional[Any] = None):
        self.parser = ExplainParser()
        self.analyzer = RiskAnalyzer(knowledge_base=knowledge_base)

    def diagnose(
        self,
        sql: str,
        explain_output: Union[str, Dict[str, Any], List[Dict[str, Any]]],
    ) -> ExplainDiagnosisResult:
        plan = self.parser.parse(explain_output, sql=sql)
        findings = self.analyzer.analyze(plan)
        summary = self._build_summary(findings)
        ddl_suggestions = self._build_ddl_suggestions(sql, findings)

        return ExplainDiagnosisResult(
            sql=sql,
            findings=findings,
            summary=summary,
            optimization_sql=sql,
            ddl_suggestions=ddl_suggestions,
            plan_overview={
                "tables": [row.table for row in plan.rows],
                "total_rows_examined": plan.total_rows_examined,
                "has_full_scan": plan.has_full_scan,
                "access_types": [row.access_type for row in plan.rows],
            },
        )

    def _build_summary(self, findings: List[RiskFinding]) -> str:
        if not findings:
            return "未发现明显执行计划风险。"

        critical = [item for item in findings if item.level == "CRITICAL"]
        warning = [item for item in findings if item.level == "WARNING"]
        if critical:
            names = "、".join(item.rule_name for item in critical)
            return f"发现 {len(critical)} 个严重风险：{names}。"
        if warning:
            names = "、".join(item.rule_name for item in warning)
            return f"发现 {len(warning)} 个警告级风险：{names}。"
        return f"发现 {len(findings)} 个提示级信息，整体执行计划较优。"

    def _build_ddl_suggestions(self, sql: str, findings: List[RiskFinding]) -> List[str]:
        suggestions: List[str] = []
        rule_ids = {finding.rule_id for finding in findings}

        if "R001" in rule_ids or "R002" in rule_ids:
            if "status" in sql.lower():
                suggestions.append("CREATE INDEX idx_status_created_at ON orders (status, created_at);")
            elif "merchant_id" in sql.lower():
                suggestions.append("CREATE INDEX idx_merchant_id ON orders (merchant_id);")

        if "R006" in rule_ids and "date(" in sql.lower():
            suggestions.append(
                "-- 将 DATE(created_at)='2024-01-01' 改写为范围查询\n"
                "WHERE created_at >= '2024-01-01' AND created_at < '2024-01-02'"
            )

        return suggestions