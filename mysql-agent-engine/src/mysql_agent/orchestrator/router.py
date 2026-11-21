"""Input routing for MySQL Agent orchestrator."""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List


class DiagnosisLayer(str, Enum):
    SQL = "sql"
    INSTANCE = "instance"
    ADVANCED = "advanced"
    KNOWLEDGE = "knowledge"
    HYBRID = "hybrid"


class InputRouter:
    """Route user input to the appropriate diagnosis layer."""

    SQL_KEYWORDS = [
        r"select\s+",
        r"insert\s+",
        r"update\s+",
        r"delete\s+",
        r"explain",
        r"执行计划",
        r"索引",
        r"这条\s*sql",
        r"慢查询",
        r"怎么优化",
        r"如何改写",
    ]
    INSTANCE_KEYWORDS = [
        r"数据库.*慢",
        r"连接.*满",
        r"cpu.*高",
        r"内存.*高",
        r"io.*高",
        r"响应慢",
        r"告警",
        r"故障",
        r"异常",
        r"实例",
    ]
    ADVANCED_KEYWORDS = [
        r"死锁",
        r"deadlock",
        r"复制",
        r"主从",
        r"replication",
        r"slave",
        r"延迟",
    ]
    KNOWLEDGE_KEYWORDS = [
        r"是什么",
        r"如何",
        r"怎么",
        r"推荐",
        r"原理",
        r"error\s+\d+",
    ]

    def classify(self, user_input: str) -> Dict[str, Any]:
        if re.search(r"select\s+|insert\s+|update\s+|delete\s+", user_input, re.IGNORECASE):
            return self._result(DiagnosisLayer.SQL, 0.95, "输入包含 SQL 语句", ["explain", "index", "rewrite"])

        advanced_score = self._score_keywords(user_input, self.ADVANCED_KEYWORDS)
        if advanced_score >= 0.5:
            agents = ["deadlock"] if re.search(r"死锁|deadlock", user_input, re.IGNORECASE) else ["replication"]
            return self._result(DiagnosisLayer.ADVANCED, advanced_score, "输入描述高级场景", agents)

        sql_score = self._score_keywords(user_input, self.SQL_KEYWORDS)
        instance_score = self._score_keywords(user_input, self.INSTANCE_KEYWORDS)
        knowledge_score = self._score_keywords(user_input, self.KNOWLEDGE_KEYWORDS)

        if instance_score > sql_score and instance_score >= 0.3:
            return self._result(
                DiagnosisLayer.INSTANCE,
                instance_score,
                "输入描述实例级异常现象",
                ["root_cause", "cross_correlation"],
            )
        if sql_score > 0.3:
            return self._result(DiagnosisLayer.SQL, sql_score, "输入包含 SQL 优化需求", ["explain", "index", "rewrite"])
        if knowledge_score > 0.2:
            return self._result(DiagnosisLayer.KNOWLEDGE, knowledge_score, "输入为知识问答", ["rag"])
        return self._result(DiagnosisLayer.HYBRID, 0.5, "输入模糊，执行混合诊断", ["root_cause", "rag"])

    def _score_keywords(self, text: str, patterns: List[str]) -> float:
        lowered = text.lower()
        matches = sum(1 for pattern in patterns if re.search(pattern, lowered))
        if not patterns:
            return 0.0
        return min(matches / max(len(patterns) * 0.25, 1) * 1.5, 1.0)

    def _result(
        self,
        layer: DiagnosisLayer,
        confidence: float,
        reason: str,
        agents: List[str],
    ) -> Dict[str, Any]:
        return {
            "layer": layer.value,
            "confidence": round(confidence, 3),
            "reason": reason,
            "suggested_agents": agents,
        }
