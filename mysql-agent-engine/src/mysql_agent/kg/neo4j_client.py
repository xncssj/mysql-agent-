"""Optional Neo4j client for Phase 2 knowledge graph."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_KG_PATH = Path(__file__).resolve().parents[3] / "data/kg/mysql_kg.json"


class Neo4jKGClient:
    """Thin wrapper: load Phase-1 JSON locally, optionally push to Neo4j."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "mysql-agent")
        self._driver = None

    def connect(self):
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def load_phase1_json(path: str | Path = DEFAULT_KG_PATH) -> Dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def ping(self) -> bool:
        if self._driver is None:
            self.connect()
        assert self._driver is not None
        with self._driver.session() as session:
            result = session.run("RETURN 1 AS ok")
            return result.single()["ok"] == 1

    def upsert_entities(self, entities: Iterable[Dict[str, Any]]) -> int:
        if self._driver is None:
            self.connect()
        assert self._driver is not None
        count = 0
        cypher = (
            "MERGE (n:Entity {id: $id}) "
            "SET n.name = $name, n.type = $type, n.props = $props"
        )
        with self._driver.session() as session:
            for entity in entities:
                session.run(
                    cypher,
                    id=str(entity.get("id") or entity.get("name")),
                    name=str(entity.get("name") or entity.get("id")),
                    type=str(entity.get("type") or "Concept"),
                    props=json.dumps(entity, ensure_ascii=False),
                )
                count += 1
        return count

    def load_kg_file(self, path: str | Path = DEFAULT_KG_PATH) -> Dict[str, int]:
        payload = self.load_phase1_json(path)
        entities = payload.get("entities") or payload.get("nodes") or []
        relations = payload.get("relations") or payload.get("edges") or []
        entity_count = self.upsert_entities(entities)
        rel_count = 0
        if self._driver is None:
            self.connect()
        assert self._driver is not None
        cypher = (
            "MATCH (a:Entity {id: $src}), (b:Entity {id: $dst}) "
            "MERGE (a)-[r:RELATED {type: $type}]->(b)"
        )
        with self._driver.session() as session:
            for edge in relations:
                src = edge.get("source") or edge.get("from") or edge.get("src")
                dst = edge.get("target") or edge.get("to") or edge.get("dst")
                if not src or not dst:
                    continue
                session.run(
                    cypher,
                    src=str(src),
                    dst=str(dst),
                    type=str(edge.get("type") or edge.get("relation") or "RELATED"),
                )
                rel_count += 1
        return {"entities": entity_count, "relations": rel_count}
