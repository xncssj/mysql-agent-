"""Root cause scoring engine."""
from __future__ import annotations

from typing import Dict, List, Sequence

from .cross_correlator import CrossCorrelator
from .models import Anomaly, RootCauseCandidate, RootCauseResult
from .root_cause_rules import (
    ANOMALY_CROSS_PATTERNS,
    METRIC_ROOT_CAUSE_WEIGHTS,
    ROOT_CAUSE_DEFINITIONS,
    SEVERITY_WEIGHT,
)


class RootCauseEngine:
    """Score RC01-RC18 from anomaly events."""

    def __init__(self, cross_correlator: CrossCorrelator | None = None):
        self.cross = cross_correlator or CrossCorrelator()

    def diagnose(self, anomalies: Sequence[Anomaly]) -> RootCauseResult:
        scores: Dict[str, float] = {root_id: 0.0 for root_id in ROOT_CAUSE_DEFINITIONS}
        evidence: Dict[str, List[str]] = {root_id: [] for root_id in ROOT_CAUSE_DEFINITIONS}

        for anomaly in anomalies:
            weight = SEVERITY_WEIGHT.get(anomaly.severity, 0.5)
            mapping = METRIC_ROOT_CAUSE_WEIGHTS.get(anomaly.metric, {})
            for root_id, base_score in mapping.items():
                scores[root_id] += base_score * weight
                evidence[root_id].append(f"{anomaly.metric}={anomaly.severity}")

        metric_names = [anomaly.metric for anomaly in anomalies]
        metric_set = frozenset(metric_names)
        cross_pattern = ""
        for pattern_metrics, info in ANOMALY_CROSS_PATTERNS.items():
            if not pattern_metrics.issubset(metric_set):
                continue
            cross_pattern = str(info["pattern_id"])
            for root_id, boost in info["boosts"].items():
                scores[root_id] += float(boost)
                evidence[root_id].append(f"cross:{info['pattern_id']}")

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        candidates = [
            RootCauseCandidate(
                root_cause_id=root_id,
                name=str(ROOT_CAUSE_DEFINITIONS[root_id]["name"]),
                score=score,
                evidence=evidence[root_id],
                verify_commands=list(ROOT_CAUSE_DEFINITIONS[root_id]["verify_commands"]),
            )
            for root_id, score in ranked
            if score > 0
        ]

        top_root_cause = candidates[0].root_cause_id if candidates else ""
        if not cross_pattern:
            cross_pattern = self.cross.detect_from_metrics(metric_names)

        return RootCauseResult(
            anomalies=list(anomalies),
            root_causes=candidates,
            top_root_cause=top_root_cause,
            cross_pattern=cross_pattern,
            summary=self._build_summary(top_root_cause, cross_pattern, candidates),
        )

    def _build_summary(
        self,
        top_root_cause: str,
        cross_pattern: str,
        candidates: List[RootCauseCandidate],
    ) -> str:
        if not candidates:
            return "未识别到明确根因。"
        top_name = candidates[0].name
        if cross_pattern:
            return f"首要根因 {top_root_cause}（{top_name}），交叉模式 {cross_pattern}。"
        return f"首要根因 {top_root_cause}（{top_name}）。"
