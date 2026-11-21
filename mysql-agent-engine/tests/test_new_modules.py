"""Tests for NL2SQL, reporting, hybrid search, and prompts."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mysql_agent.agents.nl2sql_agent import NL2SQLAgent
from mysql_agent.prompts import PromptBuilder
from mysql_agent.reporting import ReportGenerator
from mysql_agent.vectorstore.bm25 import BM25Retriever
from mysql_agent.vectorstore.hybrid_search import HybridSearcher

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "data/schema/ecommerce.json"


def test_prompt_builder_render():
    builder = PromptBuilder()
    prompt = builder.render("rag_qa", context="doc", question="什么是索引?")
    assert "doc" in prompt
    assert "什么是索引?" in prompt


def test_nl2sql_diagnostic_query():
    agent = NL2SQLAgent(schema_path=str(SCHEMA_PATH))
    result = agent.generate("查询慢查询 TOP10")
    assert "performance_schema" in result.sql
    assert result.status in {"success", "partial"}


def test_nl2sql_schema_linking():
    agent = NL2SQLAgent(schema_path=str(SCHEMA_PATH))
    result = agent.generate("查询订单表的商家名称")
    assert result.schema_link["tables"]
    assert any(item["name"] == "orders" for item in result.schema_link["tables"])


def test_report_generator():
    generator = ReportGenerator()
    diagnosis = {
        "anomalies": [
            {
                "metric": "connections_pct",
                "severity": "CRITICAL",
                "description": "连接数超过阈值",
                "timestamp": "2026-01-01T00:00:00",
            }
        ],
        "root_causes": [
            {
                "root_cause_id": "RC02",
                "name": "锁竞争",
                "score": 0.9,
                "evidence": ["connections_pct=CRITICAL"],
            }
        ],
        "summary": {"critical": 1, "warning": 0},
    }
    report = generator.generate(diagnosis, "mysql-prod-01")
    markdown = generator.render_markdown(report)
    assert "mysql-prod-01" in markdown
    assert "RC02" in markdown or "锁竞争" in markdown


def test_bm25_search():
    retriever = BM25Retriever(
        ["MySQL 索引优化", "死锁排查方法", "主从复制延迟分析"]
    )
    results = retriever.search("死锁")
    assert results
    assert results[0][0] == 1


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "data/vector_index/faiss_index.bin").exists(),
    reason="vector index not built",
)
def test_hybrid_search_loads_index():
    index_path = (
        Path(__file__).resolve().parents[2]
        / "data/vector_index"
    )
    from mysql_agent.vectorstore import Embedder, FAISSIndex

    index = FAISSIndex.load(str(index_path))
    embedder = Embedder.load(str(index_path))
    searcher = HybridSearcher(index, embedder)
    results = searcher.search("索引优化", k=3)
    assert results
