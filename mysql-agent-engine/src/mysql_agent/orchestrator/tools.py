"""Function-calling style tool registry."""
from __future__ import annotations

from typing import Any, Callable, Dict, List


class ToolRegistry:
    """Register callable tools for orchestrator execution."""

    def __init__(self):
        self._tools: Dict[str, dict] = {}
        self._handlers: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, description: str, parameters: dict, handler: Callable[..., Any]) -> None:
        self._tools[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }
        self._handlers[name] = handler

    def get_definitions(self) -> List[dict]:
        return list(self._tools.values())

    def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name not in self._handlers:
            raise ValueError(f"Unknown tool: {name}")
        return self._handlers[name](**arguments)


def build_tool_registry(bundle: "AgentBundle") -> ToolRegistry:
    from .agent_bundle import AgentBundle

    assert isinstance(bundle, AgentBundle)
    registry = ToolRegistry()

    registry.register(
        name="explain_sql",
        description="分析 SQL 执行计划风险",
        parameters={
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
                "explain": {"type": "object"},
            },
            "required": ["sql", "explain"],
        },
        handler=lambda sql, explain: bundle.explain.diagnose(sql, explain).to_dict(),
    )
    registry.register(
        name="suggest_index",
        description="给出索引建议",
        parameters={
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
                "table": {"type": "string"},
                "explain": {"type": "object"},
            },
            "required": ["sql", "table"],
        },
        handler=lambda sql, table, explain=None: bundle.index.advise(sql, table, explain).to_dict(),
    )
    registry.register(
        name="rewrite_sql",
        description="改写 SQL",
        parameters={
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        },
        handler=lambda sql: bundle.rewrite.rewrite(sql).to_dict(),
    )
    registry.register(
        name="diagnose_root_cause",
        description="根据异常指标推断根因",
        parameters={
            "type": "object",
            "properties": {
                "anomalies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "severity": {"type": "string"},
                        },
                    },
                }
            },
            "required": ["anomalies"],
        },
        handler=lambda anomalies: bundle.root_cause.diagnose(anomalies).to_dict(),
    )
    registry.register(
        name="cross_correlate",
        description="多指标交叉关联分析",
        parameters={
            "type": "object",
            "properties": {"metrics": {"type": "object"}},
            "required": ["metrics"],
        },
        handler=lambda metrics: bundle.cross_correlation.analyze(metrics).to_dict(),
    )
    registry.register(
        name="analyze_deadlock",
        description="分析死锁 INNODB STATUS 文本",
        parameters={
            "type": "object",
            "properties": {"innodb_status": {"type": "string"}},
            "required": ["innodb_status"],
        },
        handler=lambda innodb_status: _deadlock_result(bundle, innodb_status),
    )
    registry.register(
        name="check_replication",
        description="检查复制状态",
        parameters={
            "type": "object",
            "properties": {"slave_status": {"type": "object"}},
            "required": ["slave_status"],
        },
        handler=lambda slave_status: bundle.replication.diagnose(slave_status).to_dict(),
    )
    if bundle.rag is not None:
        registry.register(
            name="search_knowledge",
            description="搜索 MySQL 知识库",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=lambda query: bundle.rag.query(query).__dict__,
        )
    if bundle.metrics is not None:
        registry.register(
            name="check_instance_metrics",
            description="采集实例指标并检测异常",
            parameters={
                "type": "object",
                "properties": {"duration_minutes": {"type": "integer", "default": 60}},
            },
            handler=lambda duration_minutes=60: bundle.metrics.run(duration_minutes),
        )
    if bundle.nl2sql is not None:
        registry.register(
            name="nl2sql",
            description="将自然语言转换为 SQL 查询",
            parameters={
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
            handler=lambda question: bundle.nl2sql.generate(question).to_dict(),
        )
    if bundle.report is not None:
        registry.register(
            name="generate_report",
            description="生成故障复盘报告",
            parameters={
                "type": "object",
                "properties": {
                    "instance_id": {"type": "string"},
                    "diagnosis_result": {"type": "object"},
                },
                "required": ["instance_id", "diagnosis_result"],
            },
            handler=lambda instance_id, diagnosis_result: _report_result(
                bundle, instance_id, diagnosis_result
            ),
        )
    return registry


def _report_result(bundle: "AgentBundle", instance_id: str, diagnosis_result: dict) -> dict:
    report = bundle.report.generate(diagnosis_result, instance_id)
    return {
        "report": report.to_dict(),
        "markdown": bundle.report.render_markdown(report),
        "summary": f"已生成实例 {instance_id} 的复盘报告",
    }


def _deadlock_result(bundle: "AgentBundle", innodb_status: str) -> Dict[str, Any]:
    result = bundle.deadlock.analyze(innodb_status)
    if not result:
        return {"status": "no_deadlock"}
    return result.to_dict()
