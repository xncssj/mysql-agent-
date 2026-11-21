"""Causal graph wrapper over RC rules (Phase 1; Neo4j is optional Phase 2)."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Union

from .models import Anomaly
from .root_cause_engine import RootCauseEngine
from .root_cause_rules import ROOT_CAUSE_DEFINITIONS


class MySQLCausalGraph:
    """Lightweight reverse-inference graph backed by ROOT_CAUSE_DEFINITIONS."""

    def __init__(self, definitions: Optional[Dict[str, Dict[str, object]]] = None):
        self.definitions = definitions or ROOT_CAUSE_DEFINITIONS
        self.engine = RootCauseEngine()

    def nodes(self) -> List[str]:
        return sorted(self.definitions.keys())

    def metrics_for(self, rc_id: str) -> List[str]:
        node = self.definitions.get(rc_id) or {}
        metrics = node.get("metrics") or []
        return list(metrics)  # type: ignore[arg-type]

    def reverse_infer(
        self,
        anomalies: Sequence[Union[Anomaly, Dict[str, object]]],
        *,
        top_k: int = 5,
    ) -> List[Dict[str, object]]:
        """Rank root causes from anomaly metrics (same scoring as RootCauseAgent)."""
        normalized = [
            anomaly if isinstance(anomaly, Anomaly) else Anomaly.from_dict(anomaly)
            for anomaly in anomalies
        ]
        result = self.engine.diagnose(normalized)
        ranked = []
        for item in result.root_causes[:top_k]:
            ranked.append(
                {
                    "root_cause_id": item.root_cause_id,
                    "name": item.name,
                    "score": item.score,
                    "evidence": list(item.evidence),
                }
            )
        return ranked

    def neighbors(self, rc_id: str) -> List[str]:
        """Heuristic neighbors: other RC sharing ≥1 metric."""
        seed = set(self.metrics_for(rc_id))
        if not seed:
            return []
        out = []
        for other_id, node in self.definitions.items():
            if other_id == rc_id:
                continue
            other_metrics = set(node.get("metrics") or [])
            if seed & other_metrics:
                out.append(other_id)
        return sorted(out)

    def to_networkx(self):
        """Optional NetworkX view for notebooks / Neo4j export prep."""
        import networkx as nx

        graph = nx.DiGraph()
        for rc_id, node in self.definitions.items():
            graph.add_node(rc_id, name=node.get("name", rc_id), kind="root_cause")
            for metric in node.get("metrics") or []:
                metric_id = f"M:{metric}"
                graph.add_node(metric_id, name=str(metric), kind="metric")
                graph.add_edge(metric_id, rc_id, relation="evidence_for")
        return graph
