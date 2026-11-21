"""Deadlock analysis agent."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from ..deadlock import DeadlockAnalysisResult, DeadlockAnalyzer, DeadlockParser


class DeadlockAgent:
    """Parse and classify InnoDB deadlock reports."""

    def __init__(self):
        self.parser = DeadlockParser()
        self.analyzer = DeadlockAnalyzer()

    def analyze(self, innodb_status: str) -> Optional[DeadlockAnalysisResult]:
        info = self.parser.parse(innodb_status)
        if not info:
            return None
        return self.analyzer.classify(info)

    def analyze_file(self, path: Union[str, Path]) -> Optional[DeadlockAnalysisResult]:
        content = Path(path).read_text(encoding="utf-8")
        return self.analyze(content)
