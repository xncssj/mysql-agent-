# 专栏 Notebooks 索引

引擎侧可运行实验在 `mysql-agent-engine/notebooks/`。本目录放讲次导航与最小入口说明。

| Notebook / 脚本 | 对应讲次 | 说明 |
|-----------------|---------|------|
| `01_build_vector_index.py`（引擎） | 1–2 | 构建 TF-IDF / ST 索引 |
| `02_rag_recall_smoke.ipynb` | 4 / 18 | L2 Recall 冒烟 |
| `03_causal_graph_demo.ipynb` | 11 | `MySQLCausalGraph` 反向推导 |
| `04_ab_prompt_demo.ipynb` | 16 | Prompt A/B 试验 |

启动：

```bash
cd mysql-agent-engine
pip install -e ".[dev]"
jupyter notebook notebooks/
```
