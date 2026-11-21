"""Extract index-relevant columns from SQL."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

RANGE_OPS = {">", "<", ">=", "<=", "!=", "<>", "BETWEEN", "LIKE"}
SQL_FUNCTION_PATTERN = re.compile(
    r"\b(?:DATE|YEAR|MONTH|DAY|HOUR|MINUTE|SECOND|UPPER|LOWER|TRIM|SUBSTRING|LEFT|RIGHT|CONCAT|CAST|CONVERT)\s*\(\s*([`\w.]+)\s*\)",
    re.IGNORECASE,
)


@dataclass
class SqlIndexContext:
    table: str
    select_columns: List[str]
    where_columns: List[Tuple[str, str]]
    order_columns: List[str]
    join_columns: List[str]
    has_filesort: bool = False
    function_columns: List[str] = None

    def __post_init__(self) -> None:
        if self.function_columns is None:
            self.function_columns = []


def _normalize_identifier(name: str) -> str:
    return name.strip("`\"").split(".")[-1]


def _table_alias_map(sql: str, table: str) -> dict[str, str]:
    aliases = {table: table}
    pattern = re.compile(
        rf"\bFROM\s+{re.escape(table)}\s+(?:AS\s+)?([`\w]+)|"
        rf"\bJOIN\s+{re.escape(table)}\s+(?:AS\s+)?([`\w]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(sql):
        alias = match.group(1) or match.group(2)
        if alias:
            aliases[_normalize_identifier(alias)] = table
    return aliases


def _matches_table(column_ref: str, table: str, aliases: dict[str, str]) -> bool:
    if "." not in column_ref:
        return True
    prefix = _normalize_identifier(column_ref.split(".")[0])
    return aliases.get(prefix, prefix) == table


def extract_select_columns(sql: str) -> List[str]:
    match = re.search(r"\bSELECT\s+(.*?)\s+FROM\b", sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    clause = match.group(1).strip()
    if clause == "*":
        return ["*"]
    return [_normalize_identifier(part.strip()) for part in clause.split(",") if part.strip()]


def extract_where_columns(sql: str, table: str) -> List[Tuple[str, str]]:
    aliases = _table_alias_map(sql, table)
    where_match = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|$)", sql, re.IGNORECASE | re.DOTALL)
    if not where_match:
        return []

    clause = where_match.group(1)
    columns: List[Tuple[str, str]] = []
    patterns = [
        (r"([`\w.]+)\s*(>=|<=|!=|<>|>|<)\s*", "range"),
        (r"([`\w.]+)\s+LIKE\s+", "range"),
        (r"([`\w.]+)\s+BETWEEN\s+", "range"),
        (r"([`\w.]+)\s*=\s*", "eq"),
        (r"([`\w.]+)\s+IN\s*\(", "eq"),
    ]
    for pattern, kind in patterns:
        for match in re.finditer(pattern, clause, re.IGNORECASE):
            column_ref = match.group(1)
            if _matches_table(column_ref, table, aliases):
                columns.append((_normalize_identifier(column_ref), kind))

    deduped: List[Tuple[str, str]] = []
    seen = set()
    for column, kind in columns:
        key = (column, kind)
        if key not in seen:
            seen.add(key)
            deduped.append((column, kind))
    return deduped


def extract_order_columns(sql: str, table: str) -> List[str]:
    aliases = _table_alias_map(sql, table)
    match = re.search(r"\bORDER\s+BY\s+(.+?)(?:\bLIMIT\b|$)", sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return []

    columns: List[str] = []
    for part in match.group(1).split(","):
        token = part.strip().split()[0]
        column_ref = _normalize_identifier(token)
        if _matches_table(column_ref if "." in part else column_ref, table, aliases):
            columns.append(column_ref.split(".")[-1])
    return columns


def extract_join_columns(sql: str, table: str) -> List[str]:
    aliases = _table_alias_map(sql, table)
    columns: List[str] = []
    pattern = re.compile(
        r"\bON\s+([`\w.]+)\s*=\s*([`\w.]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(sql):
        left, right = match.group(1), match.group(2)
        for column_ref in (left, right):
            if _matches_table(column_ref, table, aliases):
                columns.append(_normalize_identifier(column_ref))
    return columns


def extract_function_columns(sql: str) -> List[str]:
    return [_normalize_identifier(match.group(1)) for match in SQL_FUNCTION_PATTERN.finditer(sql)]


def analyze_sql(sql: str, table: str, has_filesort: bool = False) -> SqlIndexContext:
    return SqlIndexContext(
        table=table,
        select_columns=extract_select_columns(sql),
        where_columns=extract_where_columns(sql, table),
        order_columns=extract_order_columns(sql, table),
        join_columns=extract_join_columns(sql, table),
        has_filesort=has_filesort,
        function_columns=extract_function_columns(sql),
    )
