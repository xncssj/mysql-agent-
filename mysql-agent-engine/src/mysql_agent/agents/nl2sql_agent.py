"""NL2SQL agent with diagnostic templates and schema linking."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..nl2sql.schema_linker import SchemaLinker
from ..nl2sql.sql_validator import SQLValidator
from ..prompts import PromptBuilder


@dataclass
class NL2SQLResult:
    question: str
    sql: str
    status: str
    schema_link: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    prompt: str = ""
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "sql": self.sql,
            "status": self.status,
            "schema_link": self.schema_link,
            "warnings": self.warnings,
            "summary": self.summary,
        }


DIAGNOSTIC_TEMPLATES = {
    "慢查询": """SELECT
    DIGEST_TEXT AS sql_pattern,
    COUNT_STAR AS exec_count,
    ROUND(AVG_TIMER_WAIT / 1e9, 2) AS avg_ms,
    ROUND(MAX_TIMER_WAIT / 1e9, 2) AS max_ms
FROM performance_schema.events_statements_summary_by_digest
WHERE AVG_TIMER_WAIT > 1e9
ORDER BY AVG_TIMER_WAIT DESC
LIMIT 10""",
    "全表扫描": """SELECT
    query,
    db,
    exec_count,
    ROUND(total_latency / 1e9, 2) AS total_ms,
    no_index_used_count
FROM sys.statements_with_full_table_scans
ORDER BY total_latency DESC
LIMIT 10""",
    "锁": """SELECT
    OBJECT_SCHEMA,
    OBJECT_NAME,
    THREAD_ID,
    LOCK_TYPE,
    LOCK_DURATION
FROM performance_schema.metadata_locks
WHERE OBJECT_TYPE = 'TABLE'
  AND LOCK_STATUS = 'PENDING'
ORDER BY LOCK_DURATION DESC
LIMIT 20""",
}

BUSINESS_TEMPLATES = {
    "订单数量": """SELECT DATE(created_at) AS day, COUNT(*) AS order_count
FROM orders
WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(created_at)
ORDER BY day""",
    "商家排名": """SELECT m.name, COUNT(o.order_id) AS order_count
FROM orders o
JOIN merchants m ON o.merchant_id = m.merchant_id
GROUP BY o.merchant_id, m.name
ORDER BY order_count DESC
LIMIT 10""",
}


class NL2SQLAgent:
    """Generate SQL from natural language using templates + schema linking."""

    def __init__(
        self,
        schema_path: Optional[str] = None,
        llm_client: Optional[object] = None,
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        self.schema_linker = SchemaLinker.from_file(schema_path) if schema_path else None
        self.validator = SQLValidator(self.schema_linker)
        self.llm = llm_client
        self.prompts = prompt_builder or PromptBuilder()

    def generate(self, question: str) -> NL2SQLResult:
        schema_link = self.schema_linker.link(question) if self.schema_linker else {}
        sql = self._generate_sql(question)
        is_valid, corrected_sql, warnings = self.validator.validate(sql, question)
        prompt = ""
        if self.llm is not None and hasattr(self.llm, "complete"):
            prompt = self.prompts.render(
                "nl2sql",
                schema_description=json.dumps(schema_link, ensure_ascii=False),
                examples="",
                question=question,
            )
            try:
                corrected_sql = self.llm.complete(prompt).strip()
                is_valid, corrected_sql, warnings = self.validator.validate(corrected_sql, question)
            except Exception:
                pass

        return NL2SQLResult(
            question=question,
            sql=corrected_sql,
            status="success" if is_valid else "partial",
            schema_link=schema_link,
            warnings=warnings,
            prompt=prompt,
            summary=f"生成 SQL，状态 {('success' if is_valid else 'partial')}",
        )

    def _generate_sql(self, question: str) -> str:
        lowered = question.lower()
        for keyword, template in DIAGNOSTIC_TEMPLATES.items():
            if keyword in question or keyword.lower() in lowered:
                return template
        for keyword, template in BUSINESS_TEMPLATES.items():
            if keyword in question:
                return template
        if "最近" in question and "订单" in question:
            return BUSINESS_TEMPLATES["订单数量"]
        if "商家" in question and ("排名" in question or "top" in lowered):
            return BUSINESS_TEMPLATES["商家排名"]
        return """SELECT
    DIGEST_TEXT AS sql_pattern,
    COUNT_STAR AS exec_count,
    ROUND(AVG_TIMER_WAIT / 1e9, 2) AS avg_ms
FROM performance_schema.events_statements_summary_by_digest
ORDER BY COUNT_STAR DESC
LIMIT 10"""
