# mysql-agent-engine

LLM-driven MySQL performance analysis and automated operations engine for the
《大模型驱动的 MySQL 性能分析与自动化运维实战》column.

## Features

- Vector index + Hybrid Search (Dense FAISS + BM25)
- RAG knowledge Q&A with optional OpenAI synthesis
- Rule-based agents: EXPLAIN, Index, SQL Rewrite, Root Cause, Cross Correlation, Deadlock, Replication
- NL2SQL (template + schema linking)
- Prometheus metrics collection + anomaly detection (MK/CUSUM/MAD)
- Orchestrator (state machine) + ReAct loop (heuristic or OpenAI)
- Incident report generation
- Golden Set evaluation (35 cases, L5 baseline regression)

## Quick Start

```bash
cd mysql-agent-engine
pip install -e ".[dev]"

# Run all tests
python3.10 -m pytest -q

# Golden set eval (needs vector index)
python3.10 -m mysql_agent.eval.run \
  --golden-set ../eval/golden_set.jsonl \
  --index-path ../data/vector_index

# Unified CLI
python3.10 -m mysql_agent.cli explain --sql "SELECT * FROM orders WHERE status=1"
python3.10 -m mysql_agent.cli chat --query "数据库响应慢" --metrics-fixture tests/fixtures/metrics.json
python3.10 -m mysql_agent.cli chat --query "慢 SQL 怎么优化" --context '{"sql":"SELECT * FROM orders"}' --llm heuristic
```

## OpenAI ReAct

```bash
export OPENAI_API_KEY=sk-...
python3.10 -m mysql_agent.cli chat \
  --query "分析死锁" \
  --context '{"innodb_status_file":"../docs/.../deadlock_001.txt"}' \
  --llm openai
```

## Project Layout

```
src/mysql_agent/
  agents/          # Agent entrypoints
  explain/         # EXPLAIN parser + R001-R018
  index/           # Index rules I001-I012
  rewrite/         # SQL rewrite W001-W015
  reasoning/       # Root cause RC + cross CC
  metrics/         # Prometheus + anomaly detection
  nl2sql/          # Schema linking + SQL validator
  reporting/       # Incident report generator
  orchestrator/    # Router + state machine + ReAct
  llm/             # OpenAI + heuristic clients
  prompts/         # Prompt templates
  vectorstore/     # FAISS + BM25 + hybrid search
  eval/            # Golden set runner
```

## Column Docs

See the column docs at the repository root (`../`).
