"""Read-only MySQL connector for lab / production diagnostics."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


_WRITE_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|LOAD|CALL)\b",
    re.IGNORECASE,
)


@dataclass
class MySQLConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "readonly"
    password: str = "readonlypass"
    database: str = "ecommerce"
    readonly: bool = True

    @classmethod
    def from_env(cls) -> "MySQLConfig":
        return cls(
            host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "readonly"),
            password=os.getenv("MYSQL_PASSWORD", "readonlypass"),
            database=os.getenv("MYSQL_DATABASE", "ecommerce"),
            readonly=os.getenv("MYSQL_READONLY", "1") not in {"0", "false", "False"},
        )


class ReadOnlyMySQLClient:
    """Thin pymysql wrapper that rejects write statements when readonly=True."""

    def __init__(self, config: Optional[MySQLConfig] = None):
        self.config = config or MySQLConfig.from_env()
        self._conn = None

    def connect(self):
        import pymysql

        self._conn = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=10,
            autocommit=True,
        )
        return self

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def ping(self) -> bool:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        self._conn.ping(reconnect=True)
        return True

    def query(self, sql: str, args: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        if self.config.readonly and _WRITE_RE.search(sql):
            raise PermissionError(f"write SQL blocked in readonly mode: {sql[:80]}")
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        with self._conn.cursor() as cur:
            cur.execute(sql, args or ())
            if cur.description is None:
                return []
            return list(cur.fetchall())

    def explain(self, sql: str) -> List[Dict[str, Any]]:
        return self.query(f"EXPLAIN {sql}")

    def status_snapshot(self) -> Dict[str, Any]:
        threads = self.query("SHOW GLOBAL STATUS LIKE 'Threads_connected'")
        max_conn = self.query("SHOW GLOBAL VARIABLES LIKE 'max_connections'")
        return {
            "threads_connected": threads[0]["Value"] if threads else None,
            "max_connections": max_conn[0]["Value"] if max_conn else None,
            "database": self.config.database,
            "user": self.config.user,
        }
