#!/usr/bin/env python3
"""Minimal MySQL STATUS exporter compatible with PrometheusCollector metric names."""
from __future__ import annotations

import argparse
import http.server
import socketserver
import time
from typing import Dict
from urllib.parse import urlparse

try:
    import pymysql
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pymysql required: pip install pymysql") from exc


def fetch_metrics(host: str, port: int, user: str, password: str) -> Dict[str, float]:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        connect_timeout=5,
        read_timeout=5,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW GLOBAL STATUS")
            status = {k.lower(): float(v) for k, v in cur.fetchall() if _is_number(v)}
            cur.execute("SHOW GLOBAL VARIABLES LIKE 'max_connections'")
            row = cur.fetchone()
            max_conn = float(row[1]) if row else 151.0
    finally:
        conn.close()

    out = {
        "mysql_global_status_threads_connected": status.get("threads_connected", 0.0),
        "mysql_global_variables_max_connections": max_conn,
        "mysql_global_status_queries": status.get("queries", 0.0),
        "mysql_global_status_slow_queries": status.get("slow_queries", 0.0),
        "mysql_global_status_innodb_buffer_pool_reads": status.get("innodb_buffer_pool_reads", 0.0),
        "mysql_global_status_innodb_buffer_pool_read_requests": status.get(
            "innodb_buffer_pool_read_requests", 1.0
        ),
        "mysql_global_status_innodb_buffer_pool_pages_dirty": status.get(
            "innodb_buffer_pool_pages_dirty", 0.0
        ),
        "mysql_global_status_innodb_buffer_pool_pages_total": status.get(
            "innodb_buffer_pool_pages_total", 1.0
        ),
        "mysql_global_status_innodb_row_lock_time": status.get("innodb_row_lock_time", 0.0),
        "mysql_global_status_innodb_row_lock_waits": status.get("innodb_row_lock_waits", 0.0),
        "mysql_slave_status_seconds_behind_master": 0.0,
    }
    return out


def _is_number(value: object) -> bool:
    try:
        float(value)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


class Handler(http.server.BaseHTTPRequestHandler):
    cfg: dict = {}

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/metrics", "/"}:
            self.send_response(404)
            self.end_headers()
            return
        try:
            metrics = fetch_metrics(**self.cfg)
            body = "\n".join(f"{k} {v}" for k, v in metrics.items()) + "\n"
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:  # noqa: BLE001
            msg = f"exporter_error 1\n# {exc}\n".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="exporter")
    parser.add_argument("--password", default="exporterpass")
    parser.add_argument("--listen", default="0.0.0.0:9104")
    args = parser.parse_args()
    listen_host, listen_port = args.listen.rsplit(":", 1)
    Handler.cfg = {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "password": args.password,
    }
    # Wait until MySQL accepts connections
    for _ in range(60):
        try:
            fetch_metrics(**Handler.cfg)
            break
        except Exception:
            time.sleep(2)
    with socketserver.ThreadingTCPServer((listen_host, int(listen_port)), Handler) as httpd:
        print(f"mysqld status exporter on {args.listen}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
