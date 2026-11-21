"""Index DDL generation helpers."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .models import TableIndex
from .sql_analyzer import SqlIndexContext


def has_index_on(indexes: Sequence[TableIndex], column: str) -> bool:
    for index in indexes:
        if index.columns and index.columns[0].name == column:
            return True
    return False


def has_composite_index(indexes: Sequence[TableIndex], columns: Sequence[str]) -> bool:
    for index in indexes:
        index_cols = [col.name for col in index.columns]
        if len(index_cols) >= len(columns) and index_cols[: len(columns)] == list(columns):
            return True
    return False


def build_create_index(table: str, columns: Sequence[str], suffix: Optional[str] = None) -> str:
    clean_cols = list(columns)
    suffix = suffix or "_".join(clean_cols[:3])
    return f"CREATE INDEX idx_{table}_{suffix} ON {table} ({', '.join(clean_cols)});"


def suggest_indexes(
    context: SqlIndexContext,
    existing_indexes: Sequence[TableIndex],
    access_type: str = "ALL",
) -> List[str]:
    suggestions: List[str] = []
    eq_cols = [column for column, kind in context.where_columns if kind == "eq"]
    range_cols = [column for column, kind in context.where_columns if kind == "range"]

    if access_type.upper() == "ALL" and (eq_cols or range_cols or context.order_columns):
        composite: List[str] = []
        for column in eq_cols + range_cols + context.order_columns:
            if column not in composite:
                composite.append(column)
        if composite and not has_composite_index(existing_indexes, composite):
            suggestions.append(build_create_index(context.table, composite))

    for join_col in context.join_columns:
        if not has_index_on(existing_indexes, join_col):
            suggestions.append(build_create_index(context.table, [join_col], suffix=join_col))

    if context.has_filesort and context.order_columns:
        composite = eq_cols + context.order_columns
        composite = [column for index, column in enumerate(composite) if column not in composite[:index]]
        if composite and not has_composite_index(existing_indexes, composite):
            suggestions.append(build_create_index(context.table, composite, suffix="_".join(composite[:3])))

    if context.select_columns and context.select_columns != ["*"]:
        covering_cols = eq_cols + [col for col in context.select_columns if col not in eq_cols]
        if covering_cols and not has_composite_index(existing_indexes, covering_cols):
            suggestions.append(build_create_index(context.table, covering_cols, suffix="covering"))

    return _dedupe(suggestions)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
