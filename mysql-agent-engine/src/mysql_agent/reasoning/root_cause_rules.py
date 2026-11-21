"""Root cause definitions RC01-RC18."""
from __future__ import annotations

from typing import Dict, List

ROOT_CAUSE_DEFINITIONS: Dict[str, Dict[str, object]] = {
    "RC01": {
        "name": "缺失索引导致全表扫描",
        "metrics": ["slow_query_rate", "rows_examined_rate", "bp_hit_rate"],
        "verify_commands": ["SELECT * FROM sys.statements_with_full_table_scans LIMIT 10"],
    },
    "RC02": {
        "name": "锁等待/死锁",
        "metrics": ["row_lock_time_avg", "connections_pct", "deadlock_count"],
        "verify_commands": ["SHOW ENGINE INNODB STATUS"],
    },
    "RC03": {
        "name": "Buffer Pool 不足",
        "metrics": ["bp_hit_rate", "disk_read_rate"],
        "verify_commands": ["SHOW STATUS LIKE 'Innodb_buffer_pool%'"],
    },
    "RC04": {
        "name": "脏页刷盘压力",
        "metrics": ["dirty_pages_pct", "write_qps"],
        "verify_commands": ["SHOW STATUS LIKE 'Innodb_buffer_pool_pages_dirty'"],
    },
    "RC05": {
        "name": "连接池耗尽",
        "metrics": ["connections_pct", "qps"],
        "verify_commands": ["SHOW PROCESSLIST"],
    },
    "RC06": {
        "name": "慢 SQL 拖垮实例",
        "metrics": ["slow_query_rate", "connections_pct", "qps"],
        "verify_commands": [
            "SELECT * FROM performance_schema.events_statements_summary_by_digest "
            "ORDER BY AVG_TIMER_WAIT DESC LIMIT 5"
        ],
    },
    "RC07": {
        "name": "大事务",
        "metrics": ["row_lock_time_avg", "slow_query_rate"],
        "verify_commands": ["SELECT * FROM information_schema.innodb_trx ORDER BY trx_started"],
    },
    "RC08": {
        "name": "复制延迟",
        "metrics": ["replication_lag", "write_qps"],
        "verify_commands": ["SHOW SLAVE STATUS"],
    },
    "RC09": {
        "name": "临时表落盘",
        "metrics": ["tmp_disk_tables", "sort_merge_passes"],
        "verify_commands": ["SHOW STATUS LIKE 'Created_tmp%'"],
    },
    "RC10": {
        "name": "统计信息过期",
        "metrics": ["slow_query_rate"],
        "verify_commands": ["ANALYZE TABLE"],
    },
    "RC11": {
        "name": "磁盘 IO 瓶颈",
        "metrics": ["disk_read_rate", "bp_hit_rate"],
        "verify_commands": ["iostat -x 1"],
    },
    "RC12": {
        "name": "内存不足 OOM",
        "metrics": ["memory_usage_pct", "tmp_memory_tables"],
        "verify_commands": ["dmesg", "free -m"],
    },
    "RC13": {
        "name": "网络抖动",
        "metrics": ["aborted_connects", "connection_errors"],
        "verify_commands": ["netstat -s"],
    },
    "RC14": {
        "name": "参数配置不当",
        "metrics": ["slow_query_rate"],
        "verify_commands": ["SHOW VARIABLES"],
    },
    "RC15": {
        "name": "批量导入/删除",
        "metrics": ["write_qps", "slow_query_rate"],
        "verify_commands": ["SHOW PROCESSLIST"],
    },
    "RC16": {
        "name": "热点行竞争",
        "metrics": ["deadlock_count", "threads_running"],
        "verify_commands": ["SELECT * FROM performance_schema.data_locks"],
    },
    "RC17": {
        "name": "Metadata Lock",
        "metrics": ["mdl_locks_pending", "row_lock_time_avg"],
        "verify_commands": ["SELECT * FROM performance_schema.metadata_locks"],
    },
    "RC18": {
        "name": "主从切换",
        "metrics": ["replication_lag"],
        "verify_commands": ["SHOW SLAVE STATUS"],
    },
}

SEVERITY_WEIGHT = {
    "CRITICAL": 1.0,
    "WARNING": 0.7,
    "INFO": 0.4,
}

METRIC_ROOT_CAUSE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "slow_query_rate": {"RC01": 1.0, "RC06": 0.9, "RC07": 0.5, "RC09": 0.4, "RC10": 0.3},
    "row_lock_time_avg": {"RC02": 1.0, "RC07": 0.7, "RC16": 0.5},
    "connections_pct": {"RC02": 0.6, "RC05": 1.0, "RC06": 0.5},
    "bp_hit_rate": {"RC01": 0.8, "RC03": 1.0, "RC11": 0.6},
    "replication_lag": {"RC08": 1.0, "RC18": 0.6},
    "write_qps": {"RC04": 0.7, "RC08": 0.8, "RC15": 0.6},
    "qps": {"RC05": 0.9, "RC06": 0.5},
    "rows_examined_rate": {"RC01": 1.0},
    "dirty_pages_pct": {"RC04": 1.0},
    "tmp_disk_tables": {"RC09": 1.0},
    "deadlock_count": {"RC02": 0.8, "RC16": 1.0},
    "mdl_locks_pending": {"RC17": 1.0},
    "memory_usage_pct": {"RC12": 1.0},
    "aborted_connects": {"RC13": 1.0},
}

ANOMALY_CROSS_PATTERNS: Dict[frozenset[str], Dict[str, object]] = {
    frozenset({"connections_pct", "row_lock_time_avg"}): {
        "pattern_id": "CC01",
        "boosts": {"RC02": 1.2},
    },
    frozenset({"connections_pct", "slow_query_rate"}): {
        "pattern_id": "CC02",
        "boosts": {"RC06": 1.0},
    },
    frozenset({"dirty_pages_pct", "write_qps"}): {
        "pattern_id": "CC03",
        "boosts": {"RC04": 1.0},
    },
    frozenset({"bp_hit_rate", "slow_query_rate"}): {
        "pattern_id": "CC04",
        "boosts": {"RC01": 1.2},
    },
    frozenset({"qps", "avg_query_time"}): {
        "pattern_id": "CC05",
        "boosts": {"RC02": 0.6, "RC05": 0.6},
    },
    frozenset({"row_lock_time_avg", "slow_query_rate"}): {
        "pattern_id": "CC06",
        "boosts": {"RC02": 1.0, "RC07": 0.3},
    },
    frozenset({"replication_lag", "write_qps"}): {
        "pattern_id": "CC07",
        "boosts": {"RC08": 1.2},
    },
    frozenset({"tmp_disk_tables", "sort_merge_passes"}): {
        "pattern_id": "CC08",
        "boosts": {"RC09": 1.0},
    },
    frozenset({"disk_read_rate", "bp_hit_rate"}): {
        "pattern_id": "CC09",
        "boosts": {"RC03": 0.7, "RC11": 0.7},
    },
    frozenset({"connections_pct", "qps"}): {
        "pattern_id": "CC10",
        "boosts": {"RC05": 1.2},
    },
    frozenset({"deadlock_count", "threads_running"}): {
        "pattern_id": "CC11",
        "boosts": {"RC16": 1.0},
    },
    frozenset({"mdl_locks_pending", "row_lock_time_avg"}): {
        "pattern_id": "CC12",
        "boosts": {"RC17": 1.0},
    },
    frozenset({"memory_usage_pct", "tmp_memory_tables"}): {
        "pattern_id": "CC13",
        "boosts": {"RC12": 1.0},
    },
    frozenset({"aborted_connects", "connection_errors"}): {
        "pattern_id": "CC14",
        "boosts": {"RC13": 1.0},
    },
}

PATTERN_NAMES: Dict[str, str] = {
    "CC01": "连接×锁",
    "CC02": "连接×慢查询",
    "CC03": "脏页×写入",
    "CC04": "BP×扫描",
    "CC05": "QPS×延迟",
    "CC06": "锁×慢查询",
    "CC07": "复制×写入",
    "CC08": "临时表×排序",
    "CC09": "IO×BP",
    "CC10": "连接×QPS",
    "CC11": "死锁×并发",
    "CC12": "DDL×锁",
    "CC13": "内存×临时表",
    "CC14": "网络×超时",
}
