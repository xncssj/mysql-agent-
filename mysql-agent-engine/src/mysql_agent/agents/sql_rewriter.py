"""SQL rewrite agent."""
from __future__ import annotations

from ..rewrite import RewriteResult, SQLRewriteEngine


class SQLRewriterAgent:
    """Rule-driven SQL rewrite agent."""

    def __init__(self):
        self.engine = SQLRewriteEngine()

    def rewrite(self, sql: str) -> RewriteResult:
        return self.engine.rewrite(sql)
