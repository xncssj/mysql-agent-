"""End-to-end metrics scanning agent."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import numpy as np

from .anomaly_detector import AnomalyDetector, AnomalyEvent


class MetricsAnalysisAgent:
    """Collect Prometheus metrics and detect anomalies."""

    THRESHOLDS = {
        "connections_pct": 85,
        "slow_query_rate": 0.01,
        "bp_hit_rate": 0.95,
        "dirty_pages_pct": 75,
        "replication_lag": 300,
    }

    def __init__(self, collector, detector: AnomalyDetector | None = None):
        self.collector = collector
        self.detector = detector or AnomalyDetector(self.THRESHOLDS)

    def run(self, duration_minutes: int = 60) -> dict:
        raw = self.collector.collect_all(duration_minutes)
        prepared = self._prepare_metrics(raw)
        all_events: List[AnomalyEvent] = []

        for metric_name, series in prepared.items():
            if not series:
                continue
            values = np.array([point["value"] for point in series], dtype=float)
            timestamps = [self._format_timestamp(point["timestamp"]) for point in series]
            all_events.extend(self.detector.analyze(metric_name, values, timestamps))

        return {
            "scan_time": datetime.now().isoformat(),
            "metrics_scanned": len(prepared),
            "anomalies": [event.to_dict() for event in all_events],
            "summary": {
                "critical": sum(1 for event in all_events if event.severity == "CRITICAL"),
                "warning": sum(1 for event in all_events if event.severity == "WARNING"),
            },
        }

    def _prepare_metrics(self, raw: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
        prepared = {key: value for key, value in raw.items() if value}

        connections = raw.get("connections") or []
        max_connections = raw.get("max_connections") or []
        if connections and max_connections:
            length = min(len(connections), len(max_connections))
            prepared["connections_pct"] = []
            for idx in range(length):
                max_value = max_connections[idx]["value"]
                pct = 0.0 if max_value == 0 else connections[idx]["value"] / max_value * 100
                prepared["connections_pct"].append(
                    {
                        "timestamp": connections[idx]["timestamp"],
                        "value": pct,
                    }
                )

        return prepared

    def _format_timestamp(self, value) -> str:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
