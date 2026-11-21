"""Prompt template builder for MySQL Agent."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULT_TEMPLATES: Dict[str, str] = {
    "rag_qa": """你是 MySQL 性能分析专家。基于以下技术文档回答问题。

【参考文档】
{context}

【问题】
{question}

【回答要求】
1. 基于文档内容回答，不要编造
2. 引用文档来源（专栏/文章标题）
3. 给出具体的诊断步骤或优化建议
4. 如果文档不足以回答，明确说明

【回答】""",
    "nl2sql": """你是 MySQL 专家。根据 Schema 和示例将自然语言转换为 SQL。

## Schema
{schema_description}

## 示例
{examples}

## 问题
{question}

## SQL 查询
只输出一条可执行 SELECT 语句。""",
    "report_summary": """根据以下诊断结果生成故障复盘摘要：

实例: {instance_id}
异常: {symptoms}
根因: {root_causes}

输出 3-5 条可执行改进建议。""",
}


class PromptBuilder:
    """Load YAML templates or use built-in defaults. Supports mtime hot-reload."""

    def __init__(self, template_dir: Optional[str | Path] = None, hot_reload: bool = True):
        self.templates = dict(DEFAULT_TEMPLATES)
        self.template_dir = Path(template_dir) if template_dir else None
        self.hot_reload = hot_reload
        self._mtimes: Dict[str, float] = {}
        if self.template_dir:
            self._load_dir(self.template_dir)

    def _load_dir(self, path: Path) -> None:
        if not path.exists():
            return
        for file_path in path.glob("*.yaml"):
            self._load_file(file_path)

    def _load_file(self, file_path: Path) -> None:
        with open(file_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if isinstance(data, dict) and "template" in data:
            self.templates[file_path.stem] = data["template"]
            self._mtimes[str(file_path)] = file_path.stat().st_mtime

    def _maybe_reload(self) -> None:
        if not self.hot_reload or not self.template_dir or not self.template_dir.exists():
            return
        for file_path in self.template_dir.glob("*.yaml"):
            key = str(file_path)
            mtime = file_path.stat().st_mtime
            if self._mtimes.get(key) != mtime:
                self._load_file(file_path)

    def render(self, name: str, **kwargs: Any) -> str:
        self._maybe_reload()
        if name not in self.templates:
            raise KeyError(f"Unknown prompt template: {name}")
        return self.templates[name].format(**kwargs)

    def list_templates(self) -> list[str]:
        self._maybe_reload()
        return sorted(self.templates)
