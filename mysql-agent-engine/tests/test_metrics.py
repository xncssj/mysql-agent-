"""Tests for metrics collection and anomaly detection."""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from mysql_agent.metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector


def _series(values: list[float], start: datetime | None = None) -> list[dict]:
    start = start or datetime(2026, 1, 1, 0, 0, 0)
    return [
        {"timestamp": start + timedelta(minutes=idx * 5), "value": value}
        for idx, value in enumerate(values)
    ]


@pytest.fixture
def fixture_collector() -> PrometheusCollector:
    return PrometheusCollector(
        fixture_data={
            "connections": _series([70, 72, 74, 76, 78, 80, 82, 84, 86, 88]),
            "max_connections": _series([100] * 10),
            "slow_query_rate": _series([0.001, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009]),
            "bp_hit_rate": _series([0.99, 0.98, 0.97, 0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.90]),
            "dirty_pages_pct": _series([40, 42, 44, 46, 48, 50, 52, 54, 56, 58]),
            "replication_lag": _series([10, 12, 14, 16, 18, 20, 22, 24, 26, 28]),
        }
    )


def test_anomaly_detector_threshold_and_trend():
    detector = AnomalyDetector({"connections_pct": 85})
    values = np.array([70, 72, 74, 76, 78, 80, 82, 84, 86, 88], dtype=float)
    timestamps = [f"t{i}" for i in range(len(values))]

    events = detector.analyze("connections_pct", values, timestamps)

    assert any(event.anomaly_type.value == "阈值超限" for event in events)
    assert any(event.anomaly_type.value in {"持续上升", "持续下降"} for event in events)


def test_metrics_agent_end_to_end(fixture_collector: PrometheusCollector):
    agent = MetricsAnalysisAgent(fixture_collector)
    result = agent.run(duration_minutes=60)

    assert result["metrics_scanned"] >= 5
    assert result["summary"]["critical"] >= 1
    assert any(item["metric"] == "connections_pct" for item in result["anomalies"])


def test_prometheus_collector_fixture_mode(fixture_collector: PrometheusCollector):
    data = fixture_collector.collect_all(duration_minutes=30)
    assert "connections" in data
    assert len(data["connections"]) == 10
