"""Classify deadlock patterns."""
from __future__ import annotations

from typing import Dict, List

from .models import DeadlockAnalysisResult, DeadlockInfo, DeadlockTransaction


class DeadlockAnalyzer:
    """Classify parsed deadlock information."""

    def classify(self, info: DeadlockInfo) -> DeadlockAnalysisResult:
        t1, t2 = info.transaction_1, info.transaction_2
        if self._is_gap_lock_conflict(t1, t2):
            return self._build_result(
                info,
                deadlock_type="gap_lock",
                description="间隙锁冲突：INSERT 与 SELECT FOR UPDATE 竞争",
                suggestions=[
                    "考虑将隔离级别从 REPEATABLE READ 降为 READ COMMITTED",
                    "避免在 RR 下对范围执行 SELECT FOR UPDATE",
                ],
            )

        if self._is_lock_order_issue(t1, t2):
            return self._build_result(
                info,
                deadlock_type="lock_order",
                description="加锁顺序不一致，两个事务以不同顺序访问多张表",
                suggestions=[
                    "统一事务中的表访问顺序",
                    "按主键排序后批量更新，避免交叉加锁",
                    f"事务1涉及表: {', '.join(t1.tables_involved())}",
                    f"事务2涉及表: {', '.join(t2.tables_involved())}",
                ],
            )

        if self._is_unique_key_conflict(t1, t2):
            return self._build_result(
                info,
                deadlock_type="unique_key",
                description="唯一键冲突导致死锁",
                suggestions=[
                    "使用 INSERT IGNORE 或 ON DUPLICATE KEY UPDATE",
                    "对并发插入增加重试机制",
                ],
            )

        return self._build_result(
            info,
            deadlock_type="unknown",
            description="需结合完整 INNODB STATUS 进一步分析",
            suggestions=["检查完整 INNODB STATUS 输出", "开启 innodb_print_all_deadlocks 收集更多样本"],
        )

    def _build_result(
        self,
        info: DeadlockInfo,
        deadlock_type: str,
        description: str,
        suggestions: List[str],
    ) -> DeadlockAnalysisResult:
        return DeadlockAnalysisResult(
            timestamp=info.timestamp,
            victim=info.victim,
            deadlock_type=deadlock_type,
            description=description,
            suggestions=suggestions,
            transaction_1=info.transaction_1,
            transaction_2=info.transaction_2,
            summary=f"死锁类型 {deadlock_type}，牺牲事务 T{info.victim}",
        )

    def _is_gap_lock_conflict(self, t1: DeadlockTransaction, t2: DeadlockTransaction) -> bool:
        combined_sql = f"{t1.query_text} {t2.query_text}".upper()
        if "INSERT" not in combined_sql:
            return False
        return any(lock.mode in ("X", "S") for lock in t1.locks_waiting + t2.locks_waiting)

    def _is_lock_order_issue(self, t1: DeadlockTransaction, t2: DeadlockTransaction) -> bool:
        t1_tables = set(t1.tables_involved())
        t2_tables = set(t2.tables_involved())
        if len(t1_tables) < 2 or len(t2_tables) < 2:
            return False
        if len(t1_tables & t2_tables) < 2:
            return False

        t1_order = [lock.table for lock in t1.locks_held + t1.locks_waiting]
        t2_order = [lock.table for lock in t2.locks_held + t2.locks_waiting]
        return t1_order != t2_order

    def _is_unique_key_conflict(self, t1: DeadlockTransaction, t2: DeadlockTransaction) -> bool:
        combined_sql = f"{t1.query_text} {t2.query_text}".upper()
        return "INSERT" in combined_sql and "DUPLICATE" in combined_sql
