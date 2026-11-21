"""Statistical anomaly detection for MySQL metrics."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Sequence

import numpy as np


class AnomalyType(str, Enum):
    THRESHOLD = "阈值超限"
    TREND_UP = "持续上升"
    TREND_DOWN = "持续下降"
    CHANGEPOINT = "突变点"
    OUTLIER = "离群值"


@dataclass
class AnomalyEvent:
    metric: str
    anomaly_type: AnomalyType
    severity: str
    current_value: float
    baseline: float
    timestamp: str
    description: str

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "type": self.anomaly_type.value,
            "severity": self.severity,
            "current_value": self.current_value,
            "baseline": self.baseline,
            "timestamp": self.timestamp,
            "description": self.description,
        }


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


class AnomalyDetector:
    """MK / CUSUM / MAD / threshold anomaly detection."""

    def __init__(self, thresholds: dict | None = None):
        self.thresholds = thresholds or {}

    def detect_mk_trend(self, values: np.ndarray, alpha: float = 0.05) -> bool:
        n = len(values)
        if n < 8:
            return False

        s = 0.0
        for i in range(n - 1):
            for j in range(i + 1, n):
                s += np.sign(values[j] - values[i])

        var_s = n * (n - 1) * (2 * n + 5) / 18
        if s > 0:
            z = (s - 1) / math.sqrt(var_s)
        elif s < 0:
            z = (s + 1) / math.sqrt(var_s)
        else:
            z = 0.0

        p_value = 2 * (1 - _norm_cdf(abs(z)))
        return p_value < alpha

    def detect_cusum(self, values: np.ndarray, threshold: float = 5.0, drift: float = 0.5) -> int:
        mean = float(np.mean(values))
        std = float(np.std(values))
        if std == 0:
            return -1

        normalized = (values - mean) / std
        s_pos = np.zeros(len(normalized))
        s_neg = np.zeros(len(normalized))

        for i in range(1, len(normalized)):
            s_pos[i] = max(0.0, s_pos[i - 1] + normalized[i] - drift)
            s_neg[i] = max(0.0, s_neg[i - 1] - normalized[i] - drift)
            if s_pos[i] > threshold or s_neg[i] > threshold:
                return i
        return -1

    def detect_mad_outlier(self, values: np.ndarray, threshold: float = 3.5) -> List[int]:
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        if mad == 0:
            return []
        modified_z = 0.6745 * (values - median) / mad
        return [int(i) for i, score in enumerate(modified_z) if abs(score) > threshold]

    def analyze(
        self,
        metric_name: str,
        values: np.ndarray,
        timestamps: Sequence[str],
    ) -> List[AnomalyEvent]:
        if len(values) == 0:
            return []

        events: List[AnomalyEvent] = []
        threshold = self.thresholds.get(metric_name)

        if threshold is not None:
            current = float(values[-1])
            breached = (
                current > threshold
                if metric_name != "bp_hit_rate"
                else current < threshold
            )
            if breached:
                events.append(
                    AnomalyEvent(
                        metric=metric_name,
                        anomaly_type=AnomalyType.THRESHOLD,
                        severity="CRITICAL",
                        current_value=current,
                        baseline=float(threshold),
                        timestamp=timestamps[-1],
                        description=(
                            f"{metric_name} 当前值 {current:.4f} "
                            f"{'低于' if metric_name == 'bp_hit_rate' else '超过'}阈值 {threshold}"
                        ),
                    )
                )

        if self.detect_mk_trend(values):
            direction = "上升" if values[-1] > values[0] else "下降"
            events.append(
                AnomalyEvent(
                    metric=metric_name,
                    anomaly_type=AnomalyType.TREND_UP if direction == "上升" else AnomalyType.TREND_DOWN,
                    severity="WARNING",
                    current_value=float(values[-1]),
                    baseline=float(np.mean(values)),
                    timestamp=timestamps[-1],
                    description=f"{metric_name} 存在持续{direction}趋势",
                )
            )

        change_point = self.detect_cusum(values)
        if change_point > 0:
            events.append(
                AnomalyEvent(
                    metric=metric_name,
                    anomaly_type=AnomalyType.CHANGEPOINT,
                    severity="WARNING",
                    current_value=float(values[-1]),
                    baseline=float(np.mean(values[:change_point])),
                    timestamp=timestamps[change_point],
                    description=f"{metric_name} 在 {timestamps[change_point]} 检测到突变",
                )
            )

        outliers = self.detect_mad_outlier(values)
        if outliers:
            idx = outliers[-1]
            events.append(
                AnomalyEvent(
                    metric=metric_name,
                    anomaly_type=AnomalyType.OUTLIER,
                    severity="WARNING",
                    current_value=float(values[idx]),
                    baseline=float(np.median(values)),
                    timestamp=timestamps[idx],
                    description=f"{metric_name} 在 {len(outliers)} 个时间点检测到离群值",
                )
            )

        return events
