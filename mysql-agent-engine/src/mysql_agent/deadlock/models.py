"""Deadlock parsing models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class LockInfo:
    lock_type: str
    table: str
    index: str
    mode: str
    waiting: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "lock_type": self.lock_type,
            "table": self.table,
            "index": self.index,
            "mode": self.mode,
            "waiting": self.waiting,
        }


@dataclass
class DeadlockTransaction:
    trx_id: str
    thread_id: int
    query_text: str
    locks_held: List[LockInfo] = field(default_factory=list)
    locks_waiting: List[LockInfo] = field(default_factory=list)

    def tables_involved(self) -> List[str]:
        tables = {lock.table for lock in self.locks_held + self.locks_waiting}
        return sorted(tables)


@dataclass
class DeadlockInfo:
    timestamp: str
    transaction_1: DeadlockTransaction
    transaction_2: DeadlockTransaction
    victim: int
    raw_text: str


@dataclass
class DeadlockAnalysisResult:
    timestamp: str
    victim: int
    deadlock_type: str
    description: str
    suggestions: List[str]
    transaction_1: DeadlockTransaction
    transaction_2: DeadlockTransaction
    summary: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "victim": self.victim,
            "type": self.deadlock_type,
            "description": self.description,
            "suggestions": self.suggestions,
            "summary": self.summary,
            "transaction_1": {
                "trx_id": self.transaction_1.trx_id,
                "thread_id": self.transaction_1.thread_id,
                "query_text": self.transaction_1.query_text,
                "locks_held": [lock.to_dict() for lock in self.transaction_1.locks_held],
                "locks_waiting": [lock.to_dict() for lock in self.transaction_1.locks_waiting],
            },
            "transaction_2": {
                "trx_id": self.transaction_2.trx_id,
                "thread_id": self.transaction_2.thread_id,
                "query_text": self.transaction_2.query_text,
                "locks_held": [lock.to_dict() for lock in self.transaction_2.locks_held],
                "locks_waiting": [lock.to_dict() for lock in self.transaction_2.locks_waiting],
            },
        }
