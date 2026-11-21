# MySQL Agent 专栏 — 5 分钟快速开始

> 代码仓库：`mysql-agent-engine/`（与专栏同 monorepo）

## 1. 安装

```bash
cd mysql-agent-engine
pip install -e ".[dev]"
```

## 2. 跑单元测试

```bash
python3.10 -m pytest -q
```

## 3. 单 Agent 试用

```bash
# EXPLAIN 诊断
python3.10 -m mysql_agent.cli explain \
  --sql "SELECT * FROM orders WHERE status=1"

# 索引建议
python3.10 -m mysql_agent.cli index \
  --sql "SELECT * FROM orders WHERE status=1 ORDER BY created_at DESC" \
  --table orders

# NL2SQL（诊断 SQL 模板）
python3.10 -m mysql_agent.cli nl2sql --question "查询慢查询 TOP10"
```

## 4. ReAct 编排（推荐）

```bash
# SQL 优化链路
python3.10 -m mysql_agent.cli chat \
  --query "这条 SQL 很慢怎么优化" \
  --context '{"sql":"SELECT * FROM orders WHERE status=1","table":"orders"}'

# 实例故障链路（离线 fixture；在 mysql-agent-engine/ 下执行）
python3.10 -m mysql_agent.cli chat \
  --query "数据库响应慢，连接数也很高" \
  --metrics-fixture tests/fixtures/metrics.json

# 等价：专栏侧同内容 fixture（从仓库根目录）
# --metrics-fixture eval/fixtures/metrics.json
```

## 5. 对接 Prometheus（需监控栈）

```bash
python3.10 -m mysql_agent.cli metrics \
  --prometheus-url http://localhost:9090 \
  --duration-minutes 60
```

## 6. Golden Set 评测

```bash
python3.10 -m mysql_agent.eval.run \
  --golden-set eval/golden_set.jsonl \
  --index-path data/vector_index
```

期望：**35/35 通过**（需 vector_index 已构建）。

> 说明：`vector_index` 内的索引与模型缓存件（`tfidf_pipeline.pkl`、`faiss_index.bin`、`st_model/` 权重）体量大、可由 `chunks.jsonl` 重建，2026-10-31 起不入库、仅本地保留；重建入口见 `mysql-agent-engine/scripts/build_index.py`。

## 7. OpenAI ReAct（可选）

```bash
export OPENAI_API_KEY=sk-...
python3.10 -m mysql_agent.cli chat \
  --query "分析死锁" \
  --context '{"innodb_status_file":"eval/fixtures/deadlock_001.txt"}' \
  --llm openai
```

## 8. 下一步阅读

- [附录-端到端故障剧本](附录-端到端故障剧本.md) — 10 个生产场景
- [附录-安全与权限指南](附录-安全与权限指南.md) — 上线前必读
- [附录-文章代码评测对照表](附录-文章代码评测对照表.md) — 文章 vs 代码
