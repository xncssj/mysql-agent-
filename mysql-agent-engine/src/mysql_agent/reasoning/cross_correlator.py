"""Cross-correlation patterns CC01-CC14."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Callable, Dict, List, Sequence

from .models import CrossCorrelationHit, CrossCorrelationResult
from .root_cause_rules import PATTERN_NAMES


def _last(values: Sequence[float]) -> float:
    return float(values[-1])


def _avg(values: Sequence[float]) -> float:
    return float(mean(values)) if values else 0.0


@dataclass
class CrossPattern:
    pattern_id: str
    name: str
    metrics: List[str]
    root_cause: str
    severity: str
    check: Callable[[Dict[str, Sequence[float]]], bool]
    verify_commands: List[str]


def _build_patterns() -> List[CrossPattern]:
    return [
        CrossPattern(
            "CC01",
            "连接×锁",
            ["connections_pct", "row_lock_time_avg"],
            "RC02",
            "CRITICAL",
            lambda metrics: _last(metrics["connections_pct"]) > 80 and _last(metrics["row_lock_time_avg"]) > 1000,
            ["SHOW ENGINE INNODB STATUS", "SELECT * FROM information_schema.innodb_trx"],
        ),
        CrossPattern(
            "CC02",
            "连接×慢查询",
            ["connections_pct", "slow_query_rate"],
            "RC06",
            "WARNING",
            lambda metrics: _last(metrics["connections_pct"]) > 75 and _last(metrics["slow_query_rate"]) > 0.01,
            [
                "SELECT * FROM performance_schema.events_statements_summary_by_digest "
                "ORDER BY AVG_TIMER_WAIT DESC LIMIT 5"
            ],
        ),
        CrossPattern(
            "CC03",
            "脏页×写入",
            ["dirty_pages_pct", "write_qps"],
            "RC04",
            "WARNING",
            lambda metrics: _last(metrics["dirty_pages_pct"]) > 75
            and _last(metrics["write_qps"]) > _avg(metrics["write_qps"]) * 1.5,
            ["SHOW STATUS LIKE 'Innodb_buffer_pool_pages_dirty'"],
        ),
        CrossPattern(
            "CC04",
            "BP×扫描",
            ["bp_hit_rate", "rows_examined_rate"],
            "RC01",
            "CRITICAL",
            lambda metrics: _last(metrics["bp_hit_rate"]) < 0.95
            and _last(metrics["rows_examined_rate"]) > _avg(metrics["rows_examined_rate"]) * 2,
            ["SELECT * FROM sys.statements_with_full_table_scans LIMIT 10"],
        ),
        CrossPattern(
            "CC05",
            "QPS×延迟",
            ["qps", "avg_query_time"],
            "RC02",
            "CRITICAL",
            lambda metrics: _last(metrics["qps"]) < _avg(metrics["qps"]) * 0.7
            and _last(metrics["avg_query_time"]) > _avg(metrics["avg_query_time"]) * 2,
            ["SHOW PROCESSLIST", "SHOW ENGINE INNODB STATUS"],
        ),
        CrossPattern(
            "CC06",
            "锁×慢查询",
            ["row_lock_time_avg", "slow_query_rate"],
            "RC07",
            "CRITICAL",
            lambda metrics: _last(metrics["row_lock_time_avg"]) > 500 and _last(metrics["slow_query_rate"]) > 0.01,
            ["SELECT * FROM information_schema.innodb_trx ORDER BY trx_started"],
        ),
        CrossPattern(
            "CC07",
            "复制×写入",
            ["replication_lag", "write_qps"],
            "RC08",
            "WARNING",
            lambda metrics: _last(metrics["replication_lag"]) > 300
            and _last(metrics["write_qps"]) > _avg(metrics["write_qps"]) * 1.2,
            ["SHOW SLAVE STATUS"],
        ),
        CrossPattern(
            "CC08",
            "临时表×排序",
            ["tmp_disk_tables", "sort_merge_passes"],
            "RC09",
            "WARNING",
            lambda metrics: _last(metrics["tmp_disk_tables"]) > 10 and _last(metrics["sort_merge_passes"]) > 0,
            ["SHOW STATUS LIKE 'Created_tmp%'"],
        ),
        CrossPattern(
            "CC09",
            "IO×BP",
            ["disk_read_rate", "bp_hit_rate"],
            "RC03",
            "WARNING",
            lambda metrics: _last(metrics["disk_read_rate"]) > _avg(metrics["disk_read_rate"]) * 2
            and _last(metrics["bp_hit_rate"]) < 0.95,
            ["SHOW STATUS LIKE 'Innodb_buffer_pool%'"],
        ),
        CrossPattern(
            "CC10",
            "连接×QPS",
            ["connections_pct", "qps"],
            "RC05",
            "CRITICAL",
            lambda metrics: _last(metrics["connections_pct"]) > 70 and _last(metrics["qps"]) < _avg(metrics["qps"]) * 0.7,
            ["SHOW PROCESSLIST", "SHOW STATUS LIKE 'Threads_%'"],
        ),
        CrossPattern(
            "CC11",
            "死锁×并发",
            ["deadlock_count", "threads_running"],
            "RC16",
            "CRITICAL",
            lambda metrics: _last(metrics["deadlock_count"]) > 0
            and _last(metrics["threads_running"]) > _avg(metrics["threads_running"]) * 1.5,
            ["SELECT * FROM performance_schema.data_locks"],
        ),
        CrossPattern(
            "CC12",
            "DDL×锁",
            ["mdl_locks_pending", "row_lock_time_avg"],
            "RC17",
            "CRITICAL",
            lambda metrics: _last(metrics["mdl_locks_pending"]) > 0 and _last(metrics["row_lock_time_avg"]) > 500,
            ["SELECT * FROM performance_schema.metadata_locks"],
        ),
        CrossPattern(
            "CC13",
            "内存×临时表",
            ["memory_usage_pct", "tmp_memory_tables"],
            "RC12",
            "WARNING",
            lambda metrics: _last(metrics["memory_usage_pct"]) > 85
            and _last(metrics["tmp_memory_tables"]) > _avg(metrics["tmp_memory_tables"]) * 2,
            ["free -m"],
        ),
        CrossPattern(
            "CC14",
            "网络×超时",
            ["aborted_connects", "connection_errors"],
            "RC13",
            "WARNING",
            lambda metrics: _last(metrics["aborted_connects"]) > 10 and _last(metrics["connection_errors"]) > 0,
            ["netstat -s"],
        ),
    ]


class CrossCorrelator:
    """Match CC01-CC14 patterns against metric time series."""

    def __init__(self):
        self.patterns = _build_patterns()

    def analyze(self, metrics: Dict[str, Sequence[float]]) -> CrossCorrelationResult:
        hits: List[CrossCorrelationHit] = []
        for pattern in self.patterns:
            if not all(metric in metrics for metric in pattern.metrics):
                continue
            try:
                subset = {metric: metrics[metric] for metric in pattern.metrics}
                if not pattern.check(subset):
                    continue
            except (KeyError, IndexError, TypeError, ValueError):
                continue

            hits.append(
                CrossCorrelationHit(
                    pattern_id=pattern.pattern_id,
                    pattern_name=pattern.name,
                    root_cause=pattern.root_cause,
                    severity=pattern.severity,
                    metrics_involved=pattern.metrics,
                    verify_commands=pattern.verify_commands,
                )
            )

        top = hits[0] if hits else None
        return CrossCorrelationResult(
            hits=hits,
            top_pattern_id=top.pattern_id if top else "",
            top_root_cause=top.root_cause if top else "",
            summary=(
                f"命中交叉模式 {top.pattern_id}（{top.pattern_name}），推断根因 {top.root_cause}"
                if top
                else "未命中交叉关联模式"
            ),
        )

    def detect_from_metrics(self, metric_names: Sequence[str]) -> str:
        """Detect strongest cross pattern from anomaly metric names only."""
        metric_set = frozenset(metric_names)
        from .root_cause_rules import ANOMALY_CROSS_PATTERNS

        best_pattern = ""
        best_size = 0
        for pattern_metrics, info in ANOMALY_CROSS_PATTERNS.items():
            if pattern_metrics.issubset(metric_set) and len(pattern_metrics) > best_size:
                best_pattern = str(info["pattern_id"])
                best_size = len(pattern_metrics)
        return best_pattern

    def pattern_name(self, pattern_id: str) -> str:
        return PATTERN_NAMES.get(pattern_id, pattern_id)
