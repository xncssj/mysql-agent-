#!/usr/bin/env python3
"""Verify local lab: MySQL readonly + Prometheus scrape + metrics agent."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mysql_agent.db import ReadOnlyMySQLClient
from mysql_agent.metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector


def check_prometheus(url: str) -> dict:
    targets = f"{url.rstrip('/')}/api/v1/targets"
    with urllib.request.urlopen(targets, timeout=5) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    active = payload.get("data", {}).get("activeTargets", [])
    up = [t for t in active if t.get("health") == "up"]
    return {"targets": len(active), "up": len(up), "detail": [
        {"job": t.get("labels", {}).get("job"), "health": t.get("health")} for t in active
    ]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prometheus-url", default="http://127.0.0.1:9090")
    parser.add_argument("--wait-seconds", type=int, default=90)
    args = parser.parse_args()

    report = {"mysql": None, "prometheus": None, "metrics_agent": None, "ok": False}

    # MySQL
    client = ReadOnlyMySQLClient()
    deadline = time.time() + args.wait_seconds
    last_err = None
    while time.time() < deadline:
        try:
            client.connect()
            snap = client.status_snapshot()
            orders = client.query("SELECT COUNT(*) AS c FROM orders")
            # write should fail
            blocked = False
            try:
                client.query("DELETE FROM orders WHERE 1=0")
            except PermissionError:
                blocked = True
            report["mysql"] = {
                "ping": True,
                "snapshot": snap,
                "orders_count": orders[0]["c"] if orders else 0,
                "write_blocked": blocked,
            }
            break
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(3)
    else:
        report["mysql"] = {"ping": False, "error": last_err}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    # Prometheus
    while time.time() < deadline:
        try:
            prom = check_prometheus(args.prometheus_url)
            report["prometheus"] = prom
            if prom["up"] >= 1:
                break
        except Exception as exc:  # noqa: BLE001
            report["prometheus"] = {"error": str(exc)}
        time.sleep(3)

    collector = PrometheusCollector(prometheus_url=args.prometheus_url)
    agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))
    metrics = agent.run(duration_minutes=5)
    report["metrics_agent"] = {
        "anomaly_count": len(metrics.get("anomalies", [])) if isinstance(metrics, dict) else None,
        "keys": list(metrics.keys()) if isinstance(metrics, dict) else type(metrics).__name__,
        "preview": str(metrics)[:500],
    }
    report["ok"] = bool(report["mysql"]["ping"] and report.get("prometheus", {}).get("up", 0) >= 1)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(0 if report["ok"] else 2)


if __name__ == "__main__":
    main()
