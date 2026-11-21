"""Reasoning data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Anomaly:
    metric: str
    severity: str

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Anomaly":
        return cls(metric=data["metric"], severity=data["severity"])


@dataclass
class RootCauseCandidate:
    root_cause_id: str
    name: str
    score: float
    evidence: List[str] = field(default_factory=list)
    verify_commands: List[str] = field(default_factory=list)


@dataclass
class RootCauseResult:
    anomalies: List[Anomaly]
    root_causes: List[RootCauseCandidate]
    top_root_cause: str
    cross_pattern: str
    summary: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "anomalies": [{"metric": item.metric, "severity": item.severity} for item in self.anomalies],
            "root_causes": [
                {
                    "root_cause_id": item.root_cause_id,
                    "name": item.name,
                    "score": item.score,
                    "evidence": item.evidence,
                    "verify_commands": item.verify_commands,
                }
                for item in self.root_causes
            ],
            "top_root_cause": self.top_root_cause,
            "cross_pattern": self.cross_pattern,
            "summary": self.summary,
        }


@dataclass
class CrossCorrelationHit:
    pattern_id: str
    pattern_name: str
    root_cause: str
    severity: str
    metrics_involved: List[str]
    verify_commands: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "root_cause": self.root_cause,
            "severity": self.severity,
            "metrics_involved": self.metrics_involved,
            "verify_commands": self.verify_commands,
        }


@dataclass
class CrossCorrelationResult:
    hits: List[CrossCorrelationHit]
    top_pattern_id: str
    top_root_cause: str
    summary: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "hits": [hit.to_dict() for hit in self.hits],
            "top_pattern_id": self.top_pattern_id,
            "top_root_cause": self.top_root_cause,
            "summary": self.summary,
        }
