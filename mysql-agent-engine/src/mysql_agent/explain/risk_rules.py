"""EXPLAIN risk rules R001-R018.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List

from .models import ExplainPlan, ExplainRow, RiskLevel

SQL_FUNCTION_PATTERN = re.compile(
    r"\b(?:DATE|YEAR|MONTH|DAY|HOUR|MINUTE|SECOND|UPPER|LOWER|TRIM|SUBSTRING|LEFT|RIGHT|CONCAT|CAST|CONVERT)\s*\(\s*[`\w.]+\s*\)",
    re.IGNORECASE,
)
LIMIT_OFFSET_PATTERN = re.compile(r"\bLIMIT\s+(\d+)\s*,\s*(\d+)", re.IGNORECASE)
LIMIT_PATTERN = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)
JOIN_PATTERN = re.compile(r"\b(?:JOIN|,)\s+[`\w]+", re.IGNORECASE)
CORRELATED_SUBQUERY_PATTERN = re.compile(
    r"\bWHERE\b.+\b(?:IN|EXISTS)\s*\(\s*SELECT\b.+\bWHERE\b",
    re.IGNORECASE | re.DOTALL,
)
IMPLICIT_CONVERSION_PATTERN = re.compile(
    r"[`\w.]+\s*=\s*\d+(?:\.\d+)?(?!\s*['\"])",
    re.IGNORECASE,
)


@dataclass
class RiskPattern:
    id: str
    name: str
    description: str
    level: RiskLevel
    check: Callable[[ExplainRow, ExplainPlan], bool]
    suggestion_template: str


def _extra_contains(row: ExplainRow, keyword: str) -> bool:
    return any(keyword.lower() in item.lower() for item in row.extra)


def _sql_has_function_on_column(plan: ExplainPlan) -> bool:
    return bool(SQL_FUNCTION_PATTERN.search(plan.sql))


def _sql_has_large_offset(plan: ExplainPlan) -> bool:
    match = LIMIT_OFFSET_PATTERN.search(plan.sql)
    if not match:
        return False
    return int(match.group(1)) > 10000


def _sql_join_count(plan: ExplainPlan) -> int:
    return len(re.findall(r"\bJOIN\b", plan.sql, re.IGNORECASE))


def _sql_has_correlated_subquery(plan: ExplainPlan) -> bool:
    return bool(CORRELATED_SUBQUERY_PATTERN.search(plan.sql))


def _sql_has_large_limit_without_order(plan: ExplainPlan) -> bool:
    if re.search(r"\bORDER\s+BY\b", plan.sql, re.IGNORECASE):
        return False
    match = LIMIT_PATTERN.search(plan.sql)
    if not match:
        return False
    return int(match.group(1)) > 1000


RISK_PATTERNS: List[RiskPattern] = [
    RiskPattern(
        id="R001",
        name="全表扫描大表",
        description="对大表（rows > 10000）进行全表扫描",
        level=RiskLevel.CRITICAL,
        check=lambda row, plan: row.access_type.upper() == "ALL" and row.rows > 10000,
        suggestion_template="表 `{table}` 发生全表扫描，涉及约 {rows} 行。建议检查 WHERE 条件并补充索引。",
    ),
    RiskPattern(
        id="R002",
        name="文件排序",
        description="使用 filesort 进行排序，内存不足时会落盘",
        level=RiskLevel.CRITICAL,
        check=lambda row, plan: _extra_contains(row, "Using filesort"),
        suggestion_template="表 `{table}` 使用 filesort。建议在 ORDER BY 列上建立索引或先过滤再排序。",
    ),
    RiskPattern(
        id="R003",
        name="临时表",
        description="使用临时表，可能产生磁盘临时表",
        level=RiskLevel.CRITICAL,
        check=lambda row, plan: _extra_contains(row, "Using temporary"),
        suggestion_template="查询使用临时表。建议简化 GROUP BY / ORDER BY 或调整索引设计。",
    ),
    RiskPattern(
        id="R004",
        name="索引未使用",
        description="存在 possible_keys 但未使用任何索引",
        level=RiskLevel.WARNING,
        check=lambda row, plan: bool(row.possible_keys) and not row.key,
        suggestion_template="表 `{table}` 有可选索引但未使用。建议检查统计信息或 SQL 写法。",
    ),
    RiskPattern(
        id="R005",
        name="低效索引合并",
        description="使用 index_merge，可能不如复合索引高效",
        level=RiskLevel.WARNING,
        check=lambda row, plan: row.access_type.lower() == "index_merge"
        or _extra_contains(row, "Using index merge"),
        suggestion_template="使用索引合并。建议评估是否建立复合索引。",
    ),
    RiskPattern(
        id="R006",
        name="隐式类型转换",
        description="列上使用函数或发生隐式类型转换，可能导致索引失效",
        level=RiskLevel.WARNING,
        check=lambda row, plan: _sql_has_function_on_column(plan)
        or (
            row.access_type.upper() == "ALL"
            and bool(IMPLICIT_CONVERSION_PATTERN.search(plan.sql))
        )
        or (row.key is not None and row.ref is None and row.access_type.upper() == "ALL"),
        suggestion_template="可能发生函数包裹列或隐式类型转换。建议改写条件为范围查询并保持列类型一致。",
    ),
    RiskPattern(
        id="R007",
        name="大偏移量分页",
        description="使用 LIMIT offset, count 且 offset 很大",
        level=RiskLevel.WARNING,
        check=lambda row, plan: _sql_has_large_offset(plan),
        suggestion_template="大偏移量分页效率低。建议使用 keyset 分页或延迟关联。",
    ),
    RiskPattern(
        id="R008",
        name="覆盖索引",
        description="使用了覆盖索引，无需回表",
        level=RiskLevel.INFO,
        check=lambda row, plan: row.is_covering_index,
        suggestion_template="表 `{table}` 使用了覆盖索引，性能优秀。",
    ),
    RiskPattern(
        id="R009",
        name="索引条件下推",
        description="使用 Index Condition Pushdown 优化",
        level=RiskLevel.INFO,
        check=lambda row, plan: _extra_contains(row, "Using index condition"),
        suggestion_template="使用 ICP 优化，可减少回表次数。",
    ),
    RiskPattern(
        id="R010",
        name="常量表",
        description="表只有一行或系统表，效率最高",
        level=RiskLevel.INFO,
        check=lambda row, plan: row.access_type.lower() in ("const", "system"),
        suggestion_template="常量表访问，效率最优。",
    ),
    RiskPattern(
        id="R011",
        name="范围扫描",
        description="使用 range 访问，需要评估扫描行数",
        level=RiskLevel.INFO,
        check=lambda row, plan: row.access_type.lower() == "range",
        suggestion_template="表 `{table}` 使用 range 扫描，建议评估 rows 和索引选择性。",
    ),
    RiskPattern(
        id="R012",
        name="唯一索引等值",
        description="通过唯一索引等值访问",
        level=RiskLevel.INFO,
        check=lambda row, plan: row.access_type.lower() == "eq_ref",
        suggestion_template="表 `{table}` 使用 eq_ref 访问，通常较优。",
    ),
    RiskPattern(
        id="R013",
        name="索引等值",
        description="通过非唯一索引等值访问",
        level=RiskLevel.INFO,
        check=lambda row, plan: row.access_type.lower() == "ref",
        suggestion_template="表 `{table}` 使用 ref 访问，建议关注 rows 大小。",
    ),
    RiskPattern(
        id="R014",
        name="反向索引扫描",
        description="发生 Backward index scan",
        level=RiskLevel.WARNING,
        check=lambda row, plan: _extra_contains(row, "Backward index scan"),
        suggestion_template="发生反向索引扫描。建议检查 ORDER BY 与索引方向是否匹配。",
    ),
    RiskPattern(
        id="R015",
        name="选择性差",
        description="使用了索引但扫描行数仍然很大",
        level=RiskLevel.WARNING,
        check=lambda row, plan: bool(row.key) and row.rows > 10000,
        suggestion_template="表 `{table}` 虽使用索引 `{key}`，但 rows 仍达 {rows}。建议检查索引选择性。",
    ),
    RiskPattern(
        id="R016",
        name="多表关联过多",
        description="JOIN 表数量过多，优化器选择空间变大",
        level=RiskLevel.WARNING,
        check=lambda row, plan: _sql_join_count(plan) > 5,
        suggestion_template="JOIN 表数量超过 5 张。建议拆分查询或补充中间结果缓存。",
    ),
    RiskPattern(
        id="R017",
        name="子查询未优化",
        description="存在相关子查询，可能导致重复执行",
        level=RiskLevel.WARNING,
        check=lambda row, plan: _sql_has_correlated_subquery(plan)
        or bool(re.search(r"\bIN\s*\(\s*SELECT\b", plan.sql, re.IGNORECASE)),
        suggestion_template="存在子查询。建议评估改写为 JOIN 或 EXISTS。",
    ),
    RiskPattern(
        id="R018",
        name="不合理 LIMIT",
        description="LIMIT 较大但缺少 ORDER BY，结果不稳定",
        level=RiskLevel.WARNING,
        check=lambda row, plan: _sql_has_large_limit_without_order(plan),
        suggestion_template="LIMIT 较大但无 ORDER BY。建议补充排序或缩小返回行数。",
    ),
]