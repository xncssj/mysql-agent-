"""Schema linking for NL2SQL."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SchemaElement:
    name: str
    type: str
    table: Optional[str]
    comment: str
    synonyms: List[str]


class SchemaLinker:
    """Map natural language queries to schema elements via keyword matching."""

    def __init__(self, schema: Dict):
        self.schema = schema
        self.elements: List[SchemaElement] = []
        self._build_elements()

    @classmethod
    def from_file(cls, schema_path: str | Path) -> "SchemaLinker":
        with open(schema_path, encoding="utf-8") as handle:
            return cls(json.load(handle))

    def _build_elements(self) -> None:
        for table in self.schema.get("tables", []):
            self.elements.append(
                SchemaElement(
                    name=table["name"],
                    type="table",
                    table=None,
                    comment=table.get("comment", ""),
                    synonyms=table.get("synonyms", []),
                )
            )
            for column in table.get("columns", []):
                self.elements.append(
                    SchemaElement(
                        name=column["name"],
                        type="column",
                        table=table["name"],
                        comment=column.get("comment", ""),
                        synonyms=column.get("synonyms", []),
                    )
                )

    def link(self, query: str, top_k: int = 10) -> Dict:
        query_lower = query.lower()
        tables = []
        columns = []

        for element in self.elements:
            terms = [element.name, element.comment, *element.synonyms]
            score = 0.0
            for term in terms:
                if not term:
                    continue
                term_lower = term.lower()
                if term_lower in query_lower:
                    score += 1.0
                elif any(part in query_lower for part in re.findall(r"[\u4e00-\u9fff]+|\w+", term_lower)):
                    score += 0.5

            if score <= 0:
                continue

            if element.type == "table":
                tables.append({"name": element.name, "score": score})
            else:
                columns.append(
                    {
                        "name": element.name,
                        "table": element.table,
                        "score": score,
                    }
                )

        tables = sorted(tables, key=lambda item: item["score"], reverse=True)[:5]
        columns = sorted(columns, key=lambda item: item["score"], reverse=True)[:top_k]
        return {
            "tables": tables,
            "columns": columns,
            "reasoning": f"识别到 {len(tables)} 个相关表，{len(columns)} 个相关字段",
        }
