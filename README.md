# 《大模型驱动的 MySQL 性能分析与自动化运维实战》

一套可运行的 MySQL 性能诊断 Agent 专栏：20 讲正文 + 完整引擎源码 + Prompt 模板 + 评测集 + 知识图谱与向量索引资产。

把 MySQL 性能诊断从「人 + 经验」升级为「知识 + 规则 + Agent + 评测」的可工程化系统。

## 这套东西能做什么

| 传统 DBA 诊断 | MySQL Agent 诊断 |
|---|---|
| 翻文档、搜博客、靠经验 | 知识库 RAG + 规则引擎 + LLM |
| 单条 SQL 或实例指标割裂看 | SQL 级 ↔ 实例级自动路由与联动 |
| 结论不可复现、难评测 | Golden Set 回放 + CI 回归 |
| 故障复盘 2-4 小时 | 5-10 分钟结构化报告 |

## 四层架构

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: 工程化与落地（第 17-20 讲）                              │
│ Orchestrator / Eval / 知识积累 / 生产部署                        │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: 诊断 Agent（第 5-16 讲）                                 │
│ NL2SQL / EXPLAIN / Index / Rewrite / Metrics / RootCause / ...  │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: 知识与 Prompt（第 1-4 讲 + 第 16 讲）                    │
│ 向量索引 / Hybrid Search / Prompt 模板 / RAG 上下文              │
├─────────────────────────────────────────────────────────────────┤
│ Layer 1: 数据与规则（贯穿全专栏）                                 │
│ 18 根因 + 14 交叉 + R/I/W/RP 规则 + Golden Set                  │
└─────────────────────────────────────────────────────────────────┘
```

## 20 讲目录

**模块一：知识体系构建与 Agent 基础（1-4 讲）**

1. 专栏概览与知识库构建 — 向量知识库（切片/FAISS）+ Phase 1 轻量知识图谱
2. Hybrid Search 检索优化 — BM25 + Dense 融合，可选 Cross-Encoder 重排序
3. Prompt 基础与模板设计 — System Role、Task Template、基础组装器
4. RAG 集成与上下文构建 — 检索结果注入 Prompt、上下文质量优化

**模块二：SQL 智能分析 Agent（5-8 讲）**

5. NL2SQL / Text-to-SQL 落地
6. 执行计划自动解读 Agent
7. 索引诊断与推荐 Agent
8. SQL 改写优化 Agent

**模块三：实例级性能诊断 Agent（9-13 讲）**

9. 从 SQL 级到实例级诊断 — 诊断层级模型、Agent 路由决策
10. 指标采集与异常检测 — Prometheus + MK/CUSUM/MAD
11. 根因因果图与反向推导 — RC01–RC18、证据路径排序
12. 多维度关联诊断 — 14 种交叉模式
13. 故障复盘报告自动生成

**模块四：高级场景与工程化（14-20 讲）**

14. 死锁自动分析与解锁建议
15. 主备切换/复制延迟智能诊断
16. Prompt 高级技巧与动态优化
17. Agent 编排与工程化落地
18. 评测体系与持续迭代
19. 智能化运维与知识积累
20. 部署与生产落地

完整索引与进度见 [目录.md](目录.md)，依赖关系与阅读路径见 [全书导读](00-全书导读与架构总览.md)。

## 快速开始

```bash
cd mysql-agent-engine
pip install -e ".[dev]"
python3.10 -m pytest -q

# EXPLAIN 诊断
python3.10 -m mysql_agent.cli explain --sql "SELECT * FROM orders WHERE status=1"

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

## 仓库结构

```
.
├── 00-全书导读与架构总览.md
├── 01-知识库构建/ … 20-部署与生产落地/   # 20 讲正文
├── mysql-agent-engine/                   # 引擎源码、测试、配置与 Docker 部署
├── data/                                 # 向量索引 chunks、知识图谱 JSON
├── eval/                                 # Golden Set、RAG 评测集、fixtures、Schema
├── prompts/                              # System / Task / Few-shot Prompt 模板
├── notebooks/                            # 实验 Notebook 导航
├── assets/                               # 架构图与 Mermaid 导出图
├── tools/                                # 发布产物与图形生成脚本
├── QUICKSTART.md
├── 目录.md
└── 附录-*.md                             # 规则速查、安全指南、故障剧本、文章代码对照
```

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

## 安全与合规

- 仓库内数据库账号、密码均为本地 Demo 值，请勿用于生产。
- 生产环境请使用只读账号，并遵循 [附录-安全与权限指南.md](附录-安全与权限指南.md)。
- 向量索引基于公开技术资料构建；请勿将无授权的付费内容上传至本仓库或任何公开仓库。

## 许可

引擎代码采用 MIT 许可，见 [LICENSE](LICENSE)；专栏正文与图表版权归作者所有，转载请注明出处。
