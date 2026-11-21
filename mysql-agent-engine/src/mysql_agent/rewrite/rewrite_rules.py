"""SQL rewrite rules W001-W015."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional

from .models import RewriteFinding

RULE_PRIORITY = [
    "W007",
    "W008",
    "W001",
    "W004",
    "W005",
    "W003",
    "W012",
    "W006",
    "W009",
    "W010",
    "W011",
    "W013",
    "W014",
    "W015",
    "W002",
]


@dataclass
class RewriteRule:
    rule_id: str
    name: str
    matches: Callable[[str], bool]
    rewrite: Callable[[str], Optional[RewriteFinding]]


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _extract_outer_table(sql: str) -> str:
    match = re.search(r"\bFROM\s+([`\"\w]+)", sql, re.IGNORECASE)
    return match.group(1).strip("`\"") if match else "t"


def _rewrite_in_subquery_to_join(sql: str) -> Optional[RewriteFinding]:
    pattern = re.compile(
        r"WHERE\s+([`\"\w.]+)\s+IN\s*\(\s*SELECT\s+([`\"\w.]+)\s+FROM\s+([`\"\w.]+)\s+WHERE\s+(.+?)\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql)
    if not match:
        return None

    outer_col = match.group(1).split(".")[-1].strip("`\"")
    inner_col = match.group(2).split(".")[-1].strip("`\"")
    inner_table = match.group(3).strip("`\"")
    inner_where = match.group(4).strip()
    outer_table = _extract_outer_table(sql)

    rewritten = re.sub(
        r"SELECT\s+\*\s+FROM",
        f"SELECT {outer_table}.* FROM",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )
    rewritten = pattern.sub("", rewritten)
    rewritten = re.sub(
        rf"\bFROM\s+{outer_table}\b",
        f"FROM {outer_table} INNER JOIN {inner_table} ON {outer_table}.{outer_col} = {inner_table}.{inner_col}",
        rewritten,
        count=1,
        flags=re.IGNORECASE,
    )
    rewritten = re.sub(r"\s+WHERE\s*$", "", rewritten, flags=re.IGNORECASE)
    if inner_where:
        rewritten = re.sub(
            r"\s*$",
            f" WHERE {inner_table}.{inner_where}",
            rewritten.strip(),
        )

    return RewriteFinding(
        rule_id="W001",
        rule_name="关联子查询→JOIN",
        message="将 IN (SELECT ...) 改写为 INNER JOIN",
        rewritten_sql=_normalize(rewritten),
        explanation="避免逐行执行子查询，改为 JOIN 一次性关联",
        expected_benefit="减少子查询重复执行开销",
    )


def _rewrite_exists(sql: str) -> Optional[RewriteFinding]:
    if not re.search(r"\bEXISTS\s*\(", sql, re.IGNORECASE):
        return None
    return RewriteFinding(
        rule_id="W002",
        rule_name="关联子查询→EXISTS",
        message="EXISTS 写法通常已较优，保留原 SQL",
        rewritten_sql=sql,
        explanation="EXISTS 在半关联场景通常优于 IN",
        expected_benefit="保持现有较优执行路径",
    )


def _rewrite_or_to_union(sql: str) -> Optional[RewriteFinding]:
    where_match = re.search(r"\bWHERE\s+(.+?)(?:\bORDER\b|\bGROUP\b|\bLIMIT\b|$)", sql, re.IGNORECASE | re.DOTALL)
    if not where_match or " OR " not in where_match.group(1).upper():
        return None

    outer_table = _extract_outer_table(sql)
    conditions = re.split(r"\s+OR\s+", where_match.group(1), flags=re.IGNORECASE)
    if len(conditions) < 2:
        return None

    select_match = re.search(r"(SELECT\s+.+?\s+FROM\s+\S+)", sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        return None
    base_select = select_match.group(1)

    parts = [f"{base_select} WHERE {condition.strip()}" for condition in conditions]
    rewritten = "\nUNION ALL\n".join(parts)
    return RewriteFinding(
        rule_id="W003",
        rule_name="OR→UNION ALL",
        message="将多列 OR 条件拆分为 UNION ALL",
        rewritten_sql=rewritten,
        explanation="避免 OR 导致索引合并或全表扫描",
        expected_benefit="每个分支可独立走索引",
    )


def _rewrite_not_in_to_not_exists(sql: str) -> Optional[RewriteFinding]:
    pattern = re.compile(
        r"([`\"\w.]+)\s+NOT\s+IN\s*\(\s*SELECT\s+([`\"\w.]+)\s+FROM\s+([`\"\w.]+)",
        re.IGNORECASE,
    )
    match = pattern.search(sql)
    if not match:
        return None

    outer_col, inner_col, inner_table = match.groups()
    table_name = inner_table.strip("`\"")
    inner_column = inner_col.split(".")[-1].strip("`\"")
    outer_column = outer_col.strip("`\"")
    rewritten = pattern.sub(
        f"NOT EXISTS (SELECT 1 FROM {table_name} WHERE {table_name}.{inner_column} = {outer_column})",
        sql,
        count=1,
    )
    return RewriteFinding(
        rule_id="W004",
        rule_name="NOT IN→NOT EXISTS",
        message="NOT IN 在子查询含 NULL 时不安全，改为 NOT EXISTS",
        rewritten_sql=_normalize(rewritten),
        explanation="避免 NULL 导致的语义陷阱",
        expected_benefit="语义更安全，优化器更易半关联",
    )


def _rewrite_large_offset(sql: str) -> Optional[RewriteFinding]:
    match = re.search(r"\bLIMIT\s+(\d+)\s*,\s*(\d+)", sql, re.IGNORECASE)
    if not match:
        return None
    offset, limit = int(match.group(1)), int(match.group(2))
    if offset < 10000:
        return None

    outer_table = _extract_outer_table(sql)
    order_match = re.search(r"\bORDER\s+BY\s+([`\"\w.]+)", sql, re.IGNORECASE)
    order_col = order_match.group(1).strip("`\"") if order_match else "id"
    order_col_name = order_col.split(".")[-1]

    rewritten = re.sub(
        r"\bLIMIT\s+\d+\s*,\s*\d+\b",
        "",
        sql,
        flags=re.IGNORECASE,
    ).strip()
    rewritten = (
        f"SELECT {outer_table}.* FROM {outer_table} "
        f"INNER JOIN (SELECT {order_col_name} FROM {outer_table} "
        f"ORDER BY {order_col_name} LIMIT {limit} OFFSET {offset}) page "
        f"ON {outer_table}.{order_col_name} = page.{order_col_name}"
    )
    return RewriteFinding(
        rule_id="W005",
        rule_name="大 OFFSET 分页",
        message=f"大偏移 LIMIT {offset},{limit} 改为延迟关联分页",
        rewritten_sql=rewritten,
        explanation="避免扫描并丢弃大量偏移行",
        expected_benefit="扫描行数从 O(offset+limit) 降为 O(limit)",
    )


def _rewrite_select_star(sql: str) -> Optional[RewriteFinding]:
    if not re.search(r"\bSELECT\s+\*\s+FROM\b", sql, re.IGNORECASE):
        return None
    return RewriteFinding(
        rule_id="W006",
        rule_name="SELECT * 精简",
        message="建议只查询必要列，减少回表和网络传输",
        rewritten_sql=sql,
        explanation="SELECT * 会放大 IO 和回表成本",
        expected_benefit="降低回表和结果集大小",
    )


def _should_skip_implicit_cast(sql: str, column: str) -> bool:
    normalized = column.lower().strip("`\"")
    if normalized == "id" or normalized.endswith("_id"):
        return True
    if re.search(r"\bIN\s*\(\s*SELECT\b", sql, re.IGNORECASE):
        return True
    return False


def _rewrite_implicit_cast(sql: str) -> Optional[RewriteFinding]:
    pattern = re.compile(r"([`\"\w.]+)\s*=\s*(\d+(?:\.\d+)?)(?!\s*['\"])", re.IGNORECASE)
    match = pattern.search(sql)
    if not match:
        return None
    column = match.group(1).split(".")[-1]
    if _should_skip_implicit_cast(sql, column):
        return None
    value = match.group(2)
    rewritten = pattern.sub(f"CAST({match.group(1)} AS CHAR) = '{value}'", sql, count=1)
    return RewriteFinding(
        rule_id="W007",
        rule_name="隐式转换修正",
        message="字符串列与数字比较可能导致隐式转换",
        rewritten_sql=_normalize(rewritten),
        explanation="显式转换两侧类型，避免索引失效",
        expected_benefit="恢复索引可用性",
    )


def _rewrite_function_on_column(sql: str) -> Optional[RewriteFinding]:
    year_match = re.search(r"\bYEAR\s*\(\s*([`\"\w.]+)\s*\)\s*=\s*(\d{4})", sql, re.IGNORECASE)
    if year_match:
        column = year_match.group(1).strip("`\"")
        year = int(year_match.group(2))
        replacement = f"{column} >= '{year}-01-01' AND {column} < '{year + 1}-01-01'"
        rewritten = re.sub(
            rf"\bYEAR\s*\(\s*{re.escape(year_match.group(1))}\s*\)\s*=\s*{year}",
            replacement,
            sql,
            flags=re.IGNORECASE,
        )
        return RewriteFinding(
            rule_id="W008",
            rule_name="函数包裹列",
            message=f"YEAR({column}) 导致索引失效，改为范围条件",
            rewritten_sql=_normalize(rewritten),
            explanation="消除函数包裹列，使条件可走范围索引",
            expected_benefit=f"可走 {column} 索引",
        )

    date_match = re.search(
        r"\bDATE\s*\(\s*([`\"\w.]+)\s*\)\s*=\s*'([^']+)'",
        sql,
        re.IGNORECASE,
    )
    if date_match:
        column = date_match.group(1).strip("`\"")
        date_value = date_match.group(2)
        replacement = f"{column} >= '{date_value}' AND {column} < DATE_ADD('{date_value}', INTERVAL 1 DAY)"
        rewritten = re.sub(
            rf"\bDATE\s*\(\s*{re.escape(date_match.group(1))}\s*\)\s*=\s*'{date_value}'",
            replacement,
            sql,
            flags=re.IGNORECASE,
        )
        return RewriteFinding(
            rule_id="W008",
            rule_name="函数包裹列",
            message=f"DATE({column}) 导致索引失效，改为范围条件",
            rewritten_sql=_normalize(rewritten),
            explanation="消除函数包裹列，使条件可走范围索引",
            expected_benefit=f"可走 {column} 索引",
        )
    return None


def _rewrite_count_column(sql: str) -> Optional[RewriteFinding]:
    if not re.search(r"\bCOUNT\s*\(\s*[`\"\w.]+\s*\)", sql, re.IGNORECASE):
        return None
    rewritten = re.sub(r"\bCOUNT\s*\(\s*[`\"\w.]+\s*\)", "COUNT(*)", sql, flags=re.IGNORECASE)
    return RewriteFinding(
        rule_id="W009",
        rule_name="COUNT(col)→COUNT(*)",
        message="非 COUNT(*) 写法可统一为 COUNT(*)",
        rewritten_sql=_normalize(rewritten),
        explanation="COUNT(*) 语义更清晰",
        expected_benefit="减少不必要的列读取",
    )


def _rewrite_redundant_distinct(sql: str) -> Optional[RewriteFinding]:
    if not re.search(r"\bSELECT\s+DISTINCT\b", sql, re.IGNORECASE):
        return None
    if not re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE):
        return None
    rewritten = re.sub(r"\bSELECT\s+DISTINCT\b", "SELECT", sql, count=1, flags=re.IGNORECASE)
    return RewriteFinding(
        rule_id="W010",
        rule_name="DISTINCT 冗余",
        message="DISTINCT 与 GROUP BY 同列时 DISTINCT 冗余",
        rewritten_sql=_normalize(rewritten),
        explanation="去掉重复去重逻辑",
        expected_benefit="减少额外去重开销",
    )


def _rewrite_having_to_where(sql: str) -> Optional[RewriteFinding]:
    having_match = re.search(r"\bHAVING\s+([^;]+)", sql, re.IGNORECASE)
    if not having_match:
        return None
    condition = having_match.group(1).strip()
    if re.search(r"\b(?:SUM|COUNT|AVG|MAX|MIN)\s*\(", condition, re.IGNORECASE):
        return None
    rewritten = re.sub(r"\bHAVING\s+[^;]+", "", sql, flags=re.IGNORECASE).strip()
    if re.search(r"\bWHERE\b", rewritten, re.IGNORECASE):
        rewritten = re.sub(r"\bWHERE\b", f"WHERE {condition} AND", rewritten, count=1, flags=re.IGNORECASE)
    else:
        rewritten = re.sub(r"\bGROUP\s+BY\b", f"WHERE {condition} GROUP BY", rewritten, count=1, flags=re.IGNORECASE)
    return RewriteFinding(
        rule_id="W011",
        rule_name="HAVING→WHERE",
        message="将无聚合函数的 HAVING 条件下推到 WHERE",
        rewritten_sql=_normalize(rewritten),
        explanation="提前过滤可减少分组数据量",
        expected_benefit="减少分组前扫描行数",
    )


def _rewrite_subquery_materialization(sql: str) -> Optional[RewriteFinding]:
    base = _rewrite_in_subquery_to_join(sql)
    if not base:
        return None
    return RewriteFinding(
        rule_id="W012",
        rule_name="子查询物化",
        message="大结果集 IN (SELECT ...) 建议改写为 JOIN",
        rewritten_sql=base.rewritten_sql,
        explanation="避免子查询物化临时表",
        expected_benefit="降低临时表开销",
    )


def _rewrite_union_to_union_all(sql: str) -> Optional[RewriteFinding]:
    if not re.search(r"\bUNION\b(?!\s+ALL)", sql, re.IGNORECASE):
        return None
    rewritten = re.sub(r"\bUNION\b(?!\s+ALL)", "UNION ALL", sql, flags=re.IGNORECASE)
    return RewriteFinding(
        rule_id="W013",
        rule_name="UNION→UNION ALL",
        message="无重复风险时 UNION 可改为 UNION ALL",
        rewritten_sql=_normalize(rewritten),
        explanation="去掉去重开销",
        expected_benefit="减少临时去重",
    )


def _rewrite_leading_like(sql: str) -> Optional[RewriteFinding]:
    if not re.search(r"LIKE\s+'%", sql, re.IGNORECASE):
        return None
    return RewriteFinding(
        rule_id="W014",
        rule_name="前缀 LIKE 优化",
        message="前导 % 的 LIKE 无法走索引",
        rewritten_sql=sql,
        explanation="建议改为全文检索或反向索引方案",
        expected_benefit="识别无法索引的模糊查询",
    )


def _rewrite_join_order(sql: str) -> Optional[RewriteFinding]:
    if len(re.findall(r"\bJOIN\b", sql, re.IGNORECASE)) < 2:
        return None
    return RewriteFinding(
        rule_id="W015",
        rule_name="JOIN 顺序",
        message="多表 JOIN 建议让小表驱动大表",
        rewritten_sql=sql,
        explanation="调整 JOIN 顺序需结合表统计信息",
        expected_benefit="减少中间结果集",
    )


REWRITE_RULES: List[RewriteRule] = [
    RewriteRule("W001", "关联子查询→JOIN", lambda sql: bool(re.search(r"\bIN\s*\(\s*SELECT\b", sql, re.IGNORECASE)), _rewrite_in_subquery_to_join),
    RewriteRule("W002", "关联子查询→EXISTS", lambda sql: bool(re.search(r"\bEXISTS\s*\(", sql, re.IGNORECASE)), _rewrite_exists),
    RewriteRule("W003", "OR→UNION ALL", lambda sql: " OR " in sql.upper(), _rewrite_or_to_union),
    RewriteRule("W004", "NOT IN→NOT EXISTS", lambda sql: bool(re.search(r"\bNOT\s+IN\s*\(", sql, re.IGNORECASE)), _rewrite_not_in_to_not_exists),
    RewriteRule("W005", "大 OFFSET 分页", lambda sql: bool(re.search(r"\bLIMIT\s+(\d+)\s*,\s*(\d+)", sql, re.IGNORECASE)), _rewrite_large_offset),
    RewriteRule("W006", "SELECT * 精简", lambda sql: bool(re.search(r"\bSELECT\s+\*\s+FROM\b", sql, re.IGNORECASE)), _rewrite_select_star),
    RewriteRule(
        "W007",
        "隐式转换修正",
        lambda sql: bool(re.search(r"[`\"\w.]+\s*=\s*\d+(?:\.\d+)?(?!\s*['\"])", sql))
        and not re.search(r"\bIN\s*\(\s*SELECT\b", sql, re.IGNORECASE),
        _rewrite_implicit_cast,
    ),
    RewriteRule("W008", "函数包裹列", lambda sql: bool(re.search(r"\b(?:YEAR|DATE|MONTH|DAY)\s*\(", sql, re.IGNORECASE)), _rewrite_function_on_column),
    RewriteRule("W009", "COUNT(col)→COUNT(*)", lambda sql: bool(re.search(r"\bCOUNT\s*\(\s*[`\"\w.]+\s*\)", sql, re.IGNORECASE)), _rewrite_count_column),
    RewriteRule("W010", "DISTINCT 冗余", lambda sql: bool(re.search(r"\bSELECT\s+DISTINCT\b", sql, re.IGNORECASE) and re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE)), _rewrite_redundant_distinct),
    RewriteRule("W011", "HAVING→WHERE", lambda sql: bool(re.search(r"\bHAVING\b", sql, re.IGNORECASE)), _rewrite_having_to_where),
    RewriteRule("W012", "子查询物化", lambda sql: bool(re.search(r"\bIN\s*\(\s*SELECT\b", sql, re.IGNORECASE)), _rewrite_subquery_materialization),
    RewriteRule("W013", "UNION→UNION ALL", lambda sql: bool(re.search(r"\bUNION\b(?!\s+ALL)", sql, re.IGNORECASE)), _rewrite_union_to_union_all),
    RewriteRule("W014", "前缀 LIKE 优化", lambda sql: bool(re.search(r"LIKE\s+'%", sql, re.IGNORECASE)), _rewrite_leading_like),
    RewriteRule("W015", "JOIN 顺序", lambda sql: len(re.findall(r"\bJOIN\b", sql, re.IGNORECASE)) >= 2, _rewrite_join_order),
]

RULE_MAP = {rule.rule_id: rule for rule in REWRITE_RULES}
