"""Index rules I001-I012.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from ..explain.models import ExplainPlan, ExplainRow
from .index_advisor import build_create_index, has_composite_index, has_index_on, suggest_indexes
from .models import IndexFinding, IndexRuleLevel, TableIndex, TableSchema
from .sql_analyzer import SqlIndexContext, analyze_sql


@dataclass
class IndexRule:
    id: str
    name: str
    level: IndexRuleLevel
    check: Callable[..., Optional[IndexFinding]]


def _extra_contains(row: ExplainRow, keyword: str) -> bool:
    return any(keyword.lower() in item.lower() for item in row.extra)


class IndexRuleEngine:
    """Apply index rules against SQL, EXPLAIN, and optional schema metadata."""

    def analyze(
        self,
        sql: str,
        table: str,
        plan: ExplainPlan,
        schema: Optional[TableSchema] = None,
        unused_indexes: Optional[List[Dict[str, str]]] = None,
        redundant_indexes: Optional[List[Dict[str, str]]] = None,
    ) -> List[IndexFinding]:
        findings: List[IndexFinding] = []
        context = analyze_sql(sql, table)
        existing_indexes = schema.indexes if schema else []
        unused_indexes = unused_indexes or []
        redundant_indexes = redundant_indexes or []

        target_row = plan.get_table_plan(table) or (plan.rows[0] if plan.rows else None)
        if target_row:
            context.has_filesort = target_row.has_filesort
            findings.extend(self._check_access_path(target_row, context, existing_indexes))
            findings.extend(self._check_sort_and_functions(target_row, context, existing_indexes))
            findings.extend(self._check_covering(target_row, context, existing_indexes))

        findings.extend(self._check_join(context, existing_indexes))
        findings.extend(self._check_redundant(redundant_indexes))
        findings.extend(self._check_unused(unused_indexes))
        if schema:
            findings.extend(self._check_selectivity(schema, existing_indexes))

        return self._dedupe(findings)

    def _check_access_path(
        self,
        row: ExplainRow,
        context: SqlIndexContext,
        indexes: Sequence[TableIndex],
    ) -> List[IndexFinding]:
        findings: List[IndexFinding] = []
        if row.access_type.upper() != "ALL":
            return findings

        eq_cols = [column for column, kind in context.where_columns if kind == "eq"]
        range_cols = [column for column, kind in context.where_columns if kind == "range"]

        if range_cols and not has_composite_index(indexes, eq_cols + range_cols):
            ddl = build_create_index(context.table, eq_cols + range_cols)
            findings.append(
                IndexFinding(
                    rule_id="I002",
                    rule_name="缺失范围索引",
                    level=IndexRuleLevel.CRITICAL.value,
                    table=context.table,
                    message=f"表 {context.table} 存在范围条件，建议将范围列放在复合索引末尾",
                    suggested_ddl=ddl,
                    evidence={"range_cols": range_cols, "rows": row.rows},
                )
            )

        if eq_cols and not has_composite_index(indexes, eq_cols):
            composite = eq_cols + context.order_columns
            composite = [column for index, column in enumerate(composite) if column not in composite[:index]]
            ddl = build_create_index(context.table, composite or eq_cols)
            findings.append(
                IndexFinding(
                    rule_id="I001",
                    rule_name="缺失等值索引",
                    level=IndexRuleLevel.CRITICAL.value,
                    table=context.table,
                    message=f"表 {context.table} 全表扫描 {row.rows} 行，建议创建等值/复合索引",
                    suggested_ddl=ddl,
                    evidence={"eq_cols": eq_cols, "rows": row.rows},
                )
            )
        elif row.rows > 1000 and not indexes:
            ddl = suggest_indexes(context, indexes, access_type=row.access_type)
            findings.append(
                IndexFinding(
                    rule_id="I001",
                    rule_name="缺失等值索引",
                    level=IndexRuleLevel.CRITICAL.value,
                    table=context.table,
                    message=f"表 {context.table} 全表扫描 {row.rows} 行，建议创建索引",
                    suggested_ddl=ddl[0] if ddl else build_create_index(context.table, ["id"]),
                    evidence={"rows": row.rows},
                )
            )

        if row.possible_keys and not row.key:
            findings.append(
                IndexFinding(
                    rule_id="I008",
                    rule_name="索引列顺序错误",
                    level=IndexRuleLevel.WARNING.value,
                    table=context.table,
                    message=f"表 {context.table} 有可选索引 {row.possible_keys} 但未命中，可能列顺序不符合最左前缀",
                    evidence={"possible_keys": row.possible_keys},
                )
            )

        return findings

    def _check_sort_and_functions(
        self,
        row: ExplainRow,
        context: SqlIndexContext,
        indexes: Sequence[TableIndex],
    ) -> List[IndexFinding]:
        findings: List[IndexFinding] = []

        if row.has_filesort or context.order_columns:
            eq_cols = [column for column, kind in context.where_columns if kind == "eq"]
            composite = eq_cols + context.order_columns
            composite = [column for index, column in enumerate(composite) if column not in composite[:index]]
            if composite and not has_composite_index(indexes, composite):
                findings.append(
                    IndexFinding(
                        rule_id="I004",
                        rule_name="缺失排序索引",
                        level=IndexRuleLevel.WARNING.value,
                        table=context.table,
                        message=f"表 {context.table} 存在 ORDER BY/filesort，建议扩展复合索引覆盖排序列",
                        suggested_ddl=build_create_index(context.table, composite),
                        evidence={"order_columns": context.order_columns, "extra": row.extra},
                    )
                )

        if context.function_columns:
            findings.append(
                IndexFinding(
                    rule_id="I010",
                    rule_name="函数导致索引失效",
                    level=IndexRuleLevel.CRITICAL.value,
                    table=context.table,
                    message=f"WHERE 对列 {context.function_columns} 使用函数，导致索引失效",
                    suggested_ddl="-- 改写为范围条件，或创建生成列索引",
                    evidence={"function_columns": context.function_columns},
                )
            )

        return findings

    def _check_covering(
        self,
        row: ExplainRow,
        context: SqlIndexContext,
        indexes: Sequence[TableIndex],
    ) -> List[IndexFinding]:
        findings: List[IndexFinding] = []

        if _extra_contains(row, "Using index"):
            findings.append(
                IndexFinding(
                    rule_id="I011",
                    rule_name="覆盖索引机会",
                    level=IndexRuleLevel.INFO.value,
                    table=context.table,
                    message=f"表 {context.table} 已使用覆盖索引，查询列可由索引直接返回",
                    evidence={"select_columns": context.select_columns, "extra": row.extra},
                )
            )
            return findings

        if context.select_columns and context.select_columns != ["*"] and row.rows > 1000:
            eq_cols = [column for column, kind in context.where_columns if kind == "eq"]
            covering = eq_cols + [column for column in context.select_columns if column not in eq_cols]
            if covering and not has_composite_index(indexes, covering):
                findings.append(
                    IndexFinding(
                        rule_id="I011",
                        rule_name="覆盖索引机会",
                        level=IndexRuleLevel.INFO.value,
                        table=context.table,
                        message=f"表 {context.table} 可通过扩展索引覆盖 SELECT 列，减少回表",
                        suggested_ddl=build_create_index(context.table, covering, suffix="covering"),
                        evidence={"select_columns": context.select_columns},
                    )
                )

        return findings

    def _check_join(self, context: SqlIndexContext, indexes: Sequence[TableIndex]) -> List[IndexFinding]:
        findings: List[IndexFinding] = []
        for join_col in context.join_columns:
            if not has_index_on(indexes, join_col):
                findings.append(
                    IndexFinding(
                        rule_id="I003",
                        rule_name="缺失 JOIN 索引",
                        level=IndexRuleLevel.CRITICAL.value,
                        table=context.table,
                        message=f"表 {context.table} 的 JOIN 列 {join_col} 缺少索引",
                        suggested_ddl=build_create_index(context.table, [join_col], suffix=join_col),
                        evidence={"join_column": join_col},
                    )
                )
        return findings

    def _check_redundant(self, redundant_indexes: List[Dict[str, str]]) -> List[IndexFinding]:
        return [
            IndexFinding(
                rule_id="I005",
                rule_name="冗余索引",
                level=IndexRuleLevel.WARNING.value,
                table=item.get("table_name", ""),
                message=(
                    f"冗余索引 {item.get('redundant_index_name')}，"
                    f"被 {item.get('dominant_index_name')} 覆盖"
                ),
                suggested_ddl=(
                    f"ALTER TABLE {item.get('table_name')} "
                    f"DROP INDEX {item.get('redundant_index_name')};"
                ),
                evidence=item,
            )
            for item in redundant_indexes
        ]

    def _check_unused(self, unused_indexes: List[Dict[str, str]]) -> List[IndexFinding]:
        return [
            IndexFinding(
                rule_id="I006",
                rule_name="未使用索引",
                level=IndexRuleLevel.INFO.value,
                table=item.get("object_name", ""),
                message=f"索引 {item.get('index_name')} 长期未使用，建议评估后删除",
                suggested_ddl=(
                    f"ALTER TABLE {item.get('object_name')} DROP INDEX {item.get('index_name')};"
                ),
                evidence=item,
            )
            for item in unused_indexes
        ]

    def _check_selectivity(self, schema: TableSchema, indexes: Sequence[TableIndex]) -> List[IndexFinding]:
        findings: List[IndexFinding] = []
        if schema.row_count <= 0:
            return findings

        for index in indexes:
            if not index.columns:
                continue
            cardinality = index.columns[0].cardinality or 0
            ratio = cardinality / schema.row_count if schema.row_count else 1
            if ratio < 0.01:
                findings.append(
                    IndexFinding(
                        rule_id="I007",
                        rule_name="低选择性索引",
                        level=IndexRuleLevel.WARNING.value,
                        table=schema.table,
                        message=f"索引 {index.index_name} 选择性过低 ({ratio:.4f})",
                        suggested_ddl=f"-- 考虑前缀索引或删除索引 {index.index_name}",
                        evidence={"cardinality": cardinality, "rows": schema.row_count},
                    )
                )
            first_col = index.columns[0]
            col_type = schema.columns.get(first_col.name, "")
            if "varchar" in col_type.lower() and not first_col.sub_part and len(col_type) > 20:
                findings.append(
                    IndexFinding(
                        rule_id="I012",
                        rule_name="前缀索引可优化",
                        level=IndexRuleLevel.INFO.value,
                        table=schema.table,
                        message=f"列 {first_col.name} 适合改用前缀索引",
                        suggested_ddl=(
                            f"CREATE INDEX idx_{schema.table}_{first_col.name}_prefix "
                            f"ON {schema.table} ({first_col.name}(20));"
                        ),
                        evidence={"column": first_col.name, "type": col_type},
                    )
                )
        return findings

    def _dedupe(self, findings: List[IndexFinding]) -> List[IndexFinding]:
        seen = set()
        result: List[IndexFinding] = []
        for finding in findings:
            key = (finding.rule_id, finding.table, finding.message[:80])
            if key in seen:
                continue
            seen.add(key)
            result.append(finding)

        level_order = {
            IndexRuleLevel.CRITICAL.value: 0,
            IndexRuleLevel.WARNING.value: 1,
            IndexRuleLevel.INFO.value: 2,
        }
        result.sort(key=lambda item: (level_order.get(item.level, 3), item.rule_id))
        return result