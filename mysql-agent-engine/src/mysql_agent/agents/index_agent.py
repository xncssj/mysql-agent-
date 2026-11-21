"""Index diagnosis and recommendation agent.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..explain import ExplainParser
from ..index import IndexRuleEngine
from ..index.models import IndexFinding, TableSchema


@dataclass
class IndexAdviceResult:
    sql: str
    table: str
    findings: List[IndexFinding] = field(default_factory=list)
    ddl_suggestions: List[str] = field(default_factory=list)
    summary: str = ""
    primary_rule_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sql": self.sql,
            "table": self.table,
            "findings": [finding.to_dict() for finding in self.findings],
            "ddl_suggestions": self.ddl_suggestions,
            "summary": self.summary,
            "primary_rule_id": self.primary_rule_id,
        }


class IndexAdvisorAgent:
    """Rule-driven index advisor."""

    def __init__(self):
        self.parser = ExplainParser()
        self.engine = IndexRuleEngine()

    def advise(
        self,
        sql: str,
        table: str,
        explain: Optional[Union[str, Dict[str, Any], List[Dict[str, Any]]]] = None,
        schema: Optional[TableSchema] = None,
        unused_indexes: Optional[List[Dict[str, str]]] = None,
        redundant_indexes: Optional[List[Dict[str, str]]] = None,
    ) -> IndexAdviceResult:
        explain_payload = explain or {"type": "ALL", "rows": 1_000_000, "table": table}
        plan = self.parser.parse(explain_payload, sql=sql)
        findings = self.engine.analyze(
            sql=sql,
            table=table,
            plan=plan,
            schema=schema,
            unused_indexes=unused_indexes,
            redundant_indexes=redundant_indexes,
        )

        ddl_suggestions = [
            finding.suggested_ddl
            for finding in findings
            if finding.suggested_ddl and finding.suggested_ddl.startswith("CREATE")
        ]
        primary_rule_id = findings[0].rule_id if findings else ""

        return IndexAdviceResult(
            sql=sql,
            table=table,
            findings=findings,
            ddl_suggestions=ddl_suggestions,
            summary=self._build_summary(findings),
            primary_rule_id=primary_rule_id,
        )

    def _build_summary(self, findings: List[IndexFinding]) -> str:
        if not findings:
            return "未发现明显索引问题。"
        names = "、".join(finding.rule_name for finding in findings[:3])
        return f"识别到 {len(findings)} 条索引建议，首要规则 {findings[0].rule_id}：{names}。"