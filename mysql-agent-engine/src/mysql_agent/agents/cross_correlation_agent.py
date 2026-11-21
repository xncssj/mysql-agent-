"""Cross-correlation diagnosis agent."""
from __future__ import annotations

from typing import Dict, List, Sequence, Union

from ..reasoning import CrossCorrelationResult, CrossCorrelator


class CrossCorrelationAgent:
    """Detect CC01-CC14 patterns from metric time series."""

    def __init__(self):
        self.correlator = CrossCorrelator()

    def analyze(self, metrics: Dict[str, Sequence[Union[int, float]]]) -> CrossCorrelationResult:
        normalized = {key: [float(value) for value in values] for key, values in metrics.items()}
        return self.correlator.analyze(normalized)
