"""Root cause diagnosis agent.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Union

from ..reasoning import Anomaly, RootCauseEngine, RootCauseResult


class RootCauseAgent:
    """Infer instance root causes from anomaly events."""

    def __init__(self):
        self.engine = RootCauseEngine()

    def diagnose(self, anomalies: Sequence[Union[Anomaly, Dict[str, str]]]) -> RootCauseResult:
        normalized = [
            anomaly if isinstance(anomaly, Anomaly) else Anomaly.from_dict(anomaly)
            for anomaly in anomalies
        ]
        return self.engine.diagnose(normalized)