# Golden Set 评测集

本目录包含 MySQL Agent 专栏的评测数据。引擎侧镜像：`mysql-agent-engine/eval/`（CI 以引擎路径为准）。

## 文件说明

| 文件 | 说明 |
|------|------|
| `golden_set.jsonl` | **45 条**标准评测用例，覆盖 12 类任务 |
| `baseline.json` | **L5 回归基线**（45/45，pass_rate=1.0） |
| `rag_qa_set.jsonl` | L2 Recall 评测集（20 条，chunk_id + soft label） |
| `e2e_manual_cases.jsonl` | L4 人工标注种子（10 条，待 DBA 打分） |
| `schemas/` | L3 `report.json` / `nl2sql.json` |
| `fixtures/metrics.json` | 指标扫描 fixture（canonical） |
| `fixtures/metrics_high_connections.json` | 同上内容别名，兼容旧文档 |
| `fixtures/deadlock_001.txt` | 死锁 INNODB STATUS 样例 |
| `L2-L5-评测指南.md` | 五层评测落地说明 |

## 用例分布

| 任务类型 | 数量 | 对应讲次 |
|---------|------|---------|
| explain_diagnosis | 5 | 第 6 讲 R001-R018 |
| index_advice | 3 | 第 7 讲 I001-I012 |
| sql_rewrite | 3 | 第 8 讲 W001-W015 |
| root_cause | 5 | 第 11 讲 RC01-RC18 |
| cross_correlation | 12 | 第 12 讲 CC01-CC14 |
| deadlock_parse | 2 | 第 14 讲 |
| replication | 3 | 第 15 讲 RP001-RP010 |
| rag_retrieval | 3 | 第 4 讲 |
| nl2sql | 3 | 第 5 讲 |
| report_generation | 2 | 第 13 讲 |
| metrics_scan | 2 | 第 10 讲 |
| orchestrator_e2e | 2 | 第 17 讲 |

## 运行方式

```bash
cd mysql-agent-engine
pip install -e ".[dev]"

# CI 迷你索引（无 GeekTime 语料）
python3.10 scripts/build_ci_index.py --output data/ci_vector_index

python3.10 -m mysql_agent.eval.run_all \
  --golden-set eval/golden_set.jsonl \
  --index-path data/ci_vector_index \
  --baseline eval/baseline.json

python3.10 -m mysql_agent.eval.run_rag_recall \
  --qa-set eval/rag_qa_set_ci.jsonl \
  --index-path data/ci_vector_index

python3.10 -m mysql_agent.eval.validate_schema
```
