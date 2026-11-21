# MySQL Agent：配套代码与案例

《大模型驱动的 MySQL 性能分析与自动化运维实战》专栏的公开代码与案例库。

本仓库**只放可运行代码与案例资产**，不收录专栏正文；20 讲正文在微信公众号发布。仓库内的引擎、Prompt、评测集与 fixtures 均可独立运行，数据已完成脱敏。

## 内容一览

| 目录 | 内容 |
|------|------|
| [`mysql-agent-engine/`](mysql-agent-engine/) | 引擎源码：知识库/RAG、Hybrid Search、NL2SQL、EXPLAIN、索引诊断、SQL 改写、指标异常检测、根因推理、死锁/复制诊断、Orchestrator + ReAct、报告生成、评测 |
| [`data/`](data/) | 向量索引 chunks（1303 条）与 Phase 1 知识图谱 JSON |
| [`eval/`](eval/) | Golden Set、RAG 问答集、E2E 用例、fixtures、JSON Schema 与评测指南 |
| [`prompts/`](prompts/) | System / Task / Few-shot Prompt 模板与实验记录 |
| [`notebooks/`](notebooks/) | 实验 Notebook 导航与最小入口 |
| [`QUICKSTART.md`](QUICKSTART.md) | 5 分钟快速开始 |

## 能力范围

- 向量知识库 + Hybrid Search（Dense FAISS + BM25）
- RAG 知识问答（可选 OpenAI 合成）
- 规则 Agent：EXPLAIN、索引推荐、SQL 改写、根因推理、多维交叉
- NL2SQL（模板 + Schema Linking）
- Prometheus 指标采集 + 异常检测（MK / CUSUM / MAD）
- Orchestrator 状态机 + ReAct 循环
- 死锁解析、主备复制延迟诊断、故障复盘报告
- Golden Set 评测与 L5 回归基线

## 快速开始

```bash
cd mysql-agent-engine
pip install -e ".[dev]"
python3.10 -m pytest -q

# EXPLAIN 诊断
python3.10 -m mysql_agent.cli explain --sql "SELECT * FROM orders WHERE status=1"

# 索引建议
python3.10 -m mysql_agent.cli index \
  --sql "SELECT * FROM orders WHERE status=1 ORDER BY created_at DESC" \
  --table orders

# ReAct 编排：SQL 优化
python3.10 -m mysql_agent.cli chat \
  --query "这条 SQL 很慢怎么优化" \
  --context '{"sql":"SELECT * FROM orders WHERE status=1","table":"orders"}'

# 实例故障链路（离线 fixture）
python3.10 -m mysql_agent.cli chat \
  --query "数据库响应慢，连接数也很高" \
  --metrics-fixture tests/fixtures/metrics.json
```

更多命令、Golden Set 评测与 OpenAI 接入见 [QUICKSTART.md](QUICKSTART.md)。

## 评测

| 层级 | 内容 | 当前基线 |
|---|---|---|
| L1 Golden Set | 45 条标准用例 | 45/45 |
| L2 RAG Recall | 20 条问答集 | mean≈0.66 |
| L3 Schema | Prompt/Agent 输出校验 | 已建 |
| L4 E2E | 50 条端到端用例 | auto 50/50 |
| L5 回归 | baseline + CI | 已建 |

详见 [eval/L2-L5-评测指南.md](eval/L2-L5-评测指南.md)。

## 环境要求

- Python 3.10+
- MySQL 8.0（本地 Lab 可用 `docker compose --profile lab`）
- 可选：Prometheus、Neo4j、OpenAI API Key（不配置时走离线规则与 heuristic 链路）
- 向量索引二进制（`faiss_index.bin`、`tfidf_pipeline.pkl`、`st_model/`）不入库，可由 `data/vector_index/chunks.jsonl` 重建；重建入口见 `mysql-agent-engine/scripts/build_index.py`，未构建时相关测试自动跳过

## 安全与合规

- 仓库内数据库账号、密码均为本地 Demo 值，请勿用于生产。
- 生产环境请使用只读账号，并遵循 `mysql-agent-engine/docs/LAB.md` 的只读验证流程。
- 请勿将无授权的付费内容上传至本仓库或任何公开仓库。

## 许可

引擎代码采用 MIT 许可，见 [LICENSE](LICENSE)；专栏正文与图表版权归作者所有，转载请注明出处。
