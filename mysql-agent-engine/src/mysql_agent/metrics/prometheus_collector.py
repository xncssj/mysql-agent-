"""Prometheus metrics collector for MySQL instances."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PrometheusCollector:
  """Pull MySQL metrics from Prometheus query_range API."""

  QUERIES = {
      "connections": "mysql_global_status_threads_connected",
      "max_connections": "mysql_global_variables_max_connections",
      "qps": "rate(mysql_global_status_queries[1m])",
      "slow_query_rate": "rate(mysql_global_status_slow_queries[5m])",
      "bp_hit_rate": (
          "1 - rate(mysql_global_status_innodb_buffer_pool_reads[5m]) "
          "/ rate(mysql_global_status_innodb_buffer_pool_read_requests[5m])"
      ),
      "dirty_pages_pct": (
          "mysql_global_status_innodb_buffer_pool_pages_dirty "
          "/ mysql_global_status_innodb_buffer_pool_pages_total * 100"
      ),
      "row_lock_time_avg": (
          "rate(mysql_global_status_innodb_row_lock_time[5m]) "
          "/ rate(mysql_global_status_innodb_row_lock_waits[5m])"
      ),
      "replication_lag": "mysql_slave_status_seconds_behind_master",
  }

  def __init__(
      self,
      prometheus_url: str = "http://localhost:9090",
      timeout: float = 10.0,
      fixture_data: Optional[Dict[str, List[dict]]] = None,
  ):
      self.prometheus_url = prometheus_url.rstrip("/")
      self.timeout = timeout
      self.fixture_data = fixture_data

  def query_range(
      self,
      promql: str,
      start: datetime,
      end: datetime,
      step: str = "15s",
  ) -> List[dict]:
      if self.fixture_data is not None:
          return []

      params = urlencode(
          {
              "query": promql,
              "start": start.timestamp(),
              "end": end.timestamp(),
              "step": step,
          }
      )
      request = Request(f"{self.prometheus_url}/api/v1/query_range?{params}")
      with urlopen(request, timeout=self.timeout) as response:
          payload = json.loads(response.read().decode("utf-8"))

      data = payload.get("data", {}).get("result", [])
      if not data:
          return []

      return [
          {"timestamp": datetime.fromtimestamp(float(ts)), "value": float(val)}
          for ts, val in data[0]["values"]
      ]

  def collect_all(self, duration_minutes: int = 60) -> Dict[str, List[dict]]:
      if self.fixture_data is not None:
          return {key: list(values) for key, values in self.fixture_data.items()}

      end = datetime.now()
      start = end - timedelta(minutes=duration_minutes)
      results: Dict[str, List[dict]] = {}
      for name, promql in self.QUERIES.items():
          results[name] = self.query_range(promql, start, end)
      return results
