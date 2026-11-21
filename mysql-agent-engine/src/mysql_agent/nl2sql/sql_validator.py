"""SQL validation for NL2SQL output."""
from __future__ import annotations

import re
from typing import List, Tuple


class SQLValidator:
    """Validate generated SQL for safety and basic quality."""

    DANGEROUS = {"DROP", "TRUNCATE", "ALTER", "GRANT", "REVOKE", "DELETE", "UPDATE", "INSERT"}

    def __init__(self, schema_linker=None):
        self.schema_linker = schema_linker

    def validate(self, sql: str, original_query: str = "") -> Tuple[bool, str, List[str]]:
        warnings: List[str] = []
        stripped = sql.strip().rstrip(";")
        if not stripped:
            return False, sql, ["SQL 为空"]

        upper_sql = stripped.upper()
        first_token = upper_sql.split()[0] if upper_sql.split() else ""
        if first_token not in {"SELECT", "SHOW", "WITH"}:
            return False, sql, [f"仅允许只读查询，检测到 {first_token or '未知语句'}"]

        for keyword in self.DANGEROUS:
            if re.search(rf"\b{keyword}\b", upper_sql):
                return False, sql, [f"检测到危险操作: {keyword}"]

        if "LIMIT" not in upper_sql and "COUNT(" not in upper_sql:
            warnings.append("建议添加 LIMIT 限制结果集大小")

        if self.schema_linker is not None:
            schema_tables = {table["name"] for table in self.schema_linker.schema.get("tables", [])}
            for table in re.findall(r"\bFROM\s+([`\w]+)", stripped, re.IGNORECASE):
                table_name = table.strip("`")
                if schema_tables and table_name not in schema_tables:
                    warnings.append(f"表 '{table_name}' 可能不存在于 schema 中")

        return len([w for w in warnings if "危险" in w or "仅允许" in w]) == 0, stripped, warnings
