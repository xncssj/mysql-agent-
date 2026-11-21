"""State-machine orchestrator for MySQL Agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .agent_bundle import AgentBundle
from .router import DiagnosisLayer, InputRouter
from .tools import ToolRegistry, build_tool_registry


class OrchestratorState(str, Enum):
    ROUTING = "routing"
    SQL_DIAGNOSIS = "sql_diagnosis"
    INSTANCE_DIAGNOSIS = "instance_diagnosis"
    ADVANCED_SCENARIO = "advanced_scenario"
    KNOWLEDGE = "knowledge"
    REPORTING = "reporting"
    DONE = "done"


@dataclass
class OrchestratorStep:
    state: str
    tool: str
    summary: str
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorResult:
    query: str
    route: Dict[str, Any]
    steps: List[OrchestratorStep]
    answer: str
    final_state: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "route": self.route,
            "steps": [
                {
                    "state": step.state,
                    "tool": step.tool,
                    "summary": step.summary,
                    "result": step.result,
                }
                for step in self.steps
            ],
            "answer": self.answer,
            "final_state": self.final_state,
        }


class MySQLOrchestrator:
    """Route and execute MySQL diagnosis workflows without an LLM loop."""

    def __init__(self, bundle: AgentBundle):
        self.bundle = bundle
        self.router = InputRouter()
        self.tools = build_tool_registry(bundle)

    def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> OrchestratorResult:
        context = context or {}
        route = self.router.classify(query)
        steps: List[OrchestratorStep] = []
        layer = route["layer"]

        if layer == DiagnosisLayer.SQL.value:
            steps.extend(self._run_sql_path(context))
        elif layer == DiagnosisLayer.INSTANCE.value:
            steps.extend(self._run_instance_path(context))
        elif layer == DiagnosisLayer.ADVANCED.value:
            steps.extend(self._run_advanced_path(query, context))
        elif layer == DiagnosisLayer.KNOWLEDGE.value:
            steps.extend(self._run_knowledge_path(query))
        else:
            steps.extend(self._run_hybrid_path(query, context))

        answer = self._build_answer(route, steps)
        return OrchestratorResult(
            query=query,
            route=route,
            steps=steps,
            answer=answer,
            final_state=OrchestratorState.DONE.value,
        )

    def _run_sql_path(self, context: Dict[str, Any]) -> List[OrchestratorStep]:
        steps: List[OrchestratorStep] = []
        sql = context.get("sql")
        if not sql:
            return steps

        explain_payload = context.get("explain", {"type": "ALL", "rows": 1_000_000})
        explain_result = self.tools.execute("explain_sql", {"sql": sql, "explain": explain_payload})
        steps.append(
            OrchestratorStep(
                state=OrchestratorState.SQL_DIAGNOSIS.value,
                tool="explain_sql",
                summary=explain_result.get("summary", "完成执行计划分析"),
                result=explain_result,
            )
        )

        table = context.get("table", self._infer_table(sql))
        index_result = self.tools.execute(
            "suggest_index",
            {"sql": sql, "table": table, "explain": explain_payload},
        )
        steps.append(
            OrchestratorStep(
                state=OrchestratorState.SQL_DIAGNOSIS.value,
                tool="suggest_index",
                summary=index_result.get("summary", "完成索引建议"),
                result=index_result,
            )
        )

        rewrite_result = self.tools.execute("rewrite_sql", {"sql": sql})
        if rewrite_result.get("primary_rule_id"):
            steps.append(
                OrchestratorStep(
                    state=OrchestratorState.SQL_DIAGNOSIS.value,
                    tool="rewrite_sql",
                    summary=rewrite_result.get("summary", "完成 SQL 改写"),
                    result=rewrite_result,
                )
            )
        return steps

    def _run_instance_path(self, context: Dict[str, Any]) -> List[OrchestratorStep]:
        steps: List[OrchestratorStep] = []
        anomalies = context.get("anomalies")
        metrics_payload = context.get("metrics")

        if not anomalies and self.bundle.metrics is not None and context.get("auto_metrics", True):
            metrics_result = self.tools.execute(
                "check_instance_metrics",
                {"duration_minutes": context.get("duration_minutes", 60)},
            )
            steps.append(
                OrchestratorStep(
                    state=OrchestratorState.INSTANCE_DIAGNOSIS.value,
                    tool="check_instance_metrics",
                    summary=f"扫描 {metrics_result.get('metrics_scanned', 0)} 项指标",
                    result=metrics_result,
                )
            )
            anomalies = [
                {"metric": item["metric"], "severity": item["severity"]}
                for item in metrics_result.get("anomalies", [])
            ]

        if anomalies:
            root_result = self.tools.execute("diagnose_root_cause", {"anomalies": anomalies})
            steps.append(
                OrchestratorStep(
                    state=OrchestratorState.INSTANCE_DIAGNOSIS.value,
                    tool="diagnose_root_cause",
                    summary=root_result.get("summary", "完成根因推理"),
                    result=root_result,
                )
            )

        metrics = metrics_payload
        if metrics:
            cross_result = self.tools.execute("cross_correlate", {"metrics": metrics})
            steps.append(
                OrchestratorStep(
                    state=OrchestratorState.INSTANCE_DIAGNOSIS.value,
                    tool="cross_correlate",
                    summary=cross_result.get("summary", "完成交叉关联分析"),
                    result=cross_result,
                )
            )

        if steps and self.bundle.report is not None and context.get("generate_report", True):
            diagnosis_result = self._compose_diagnosis(steps)
            report_result = self.tools.execute(
                "generate_report",
                {
                    "instance_id": context.get("instance_id", "mysql-instance-01"),
                    "diagnosis_result": diagnosis_result,
                },
            )
            steps.append(
                OrchestratorStep(
                    state=OrchestratorState.REPORTING.value,
                    tool="generate_report",
                    summary=report_result.get("summary", "完成复盘报告"),
                    result=report_result,
                )
            )
        return steps

    def _compose_diagnosis(self, steps: List[OrchestratorStep]) -> Dict[str, Any]:
        diagnosis: Dict[str, Any] = {"anomalies": [], "root_causes": [], "steps": []}
        for step in steps:
            diagnosis["steps"].append(
                {"tool": step.tool, "summary": step.summary, "timestamp": ""}
            )
            if step.tool == "check_instance_metrics":
                diagnosis["anomalies"] = step.result.get("anomalies", [])
                diagnosis["summary"] = step.result.get("summary", {})
            if step.tool == "diagnose_root_cause":
                diagnosis["root_causes"] = step.result.get("root_causes", [])
                diagnosis["top_root_cause"] = step.result.get("top_root_cause")
        return diagnosis

    def _run_advanced_path(self, query: str, context: Dict[str, Any]) -> List[OrchestratorStep]:
        steps: List[OrchestratorStep] = []
        if context.get("innodb_status") or context.get("innodb_status_file"):
            status = context.get("innodb_status")
            if not status and context.get("innodb_status_file"):
                from pathlib import Path

                status = Path(context["innodb_status_file"]).read_text(encoding="utf-8")
            deadlock_result = self.tools.execute("analyze_deadlock", {"innodb_status": status})
            steps.append(
                OrchestratorStep(
                    state=OrchestratorState.ADVANCED_SCENARIO.value,
                    tool="analyze_deadlock",
                    summary=deadlock_result.get("summary", "完成死锁分析"),
                    result=deadlock_result,
                )
            )
            return steps

        slave_status = context.get("slave_status")
        if slave_status or "复制" in query or "replication" in query.lower():
            replication_result = self.tools.execute(
                "check_replication",
                {"slave_status": slave_status or {}},
            )
            steps.append(
                OrchestratorStep(
                    state=OrchestratorState.ADVANCED_SCENARIO.value,
                    tool="check_replication",
                    summary=replication_result.get("summary", "完成复制诊断"),
                    result=replication_result,
                )
            )
        return steps

    def _run_knowledge_path(self, query: str) -> List[OrchestratorStep]:
        if self.bundle.rag is None:
            return []
        rag_result = self.tools.execute("search_knowledge", {"query": query})
        return [
            OrchestratorStep(
                state=OrchestratorState.KNOWLEDGE.value,
                tool="search_knowledge",
                summary="完成知识库检索",
                result=rag_result,
            )
        ]

    def _run_hybrid_path(self, query: str, context: Dict[str, Any]) -> List[OrchestratorStep]:
        steps = self._run_instance_path(context)
        if self.bundle.rag is not None:
            steps.extend(self._run_knowledge_path(query))
        if context.get("sql"):
            steps.extend(self._run_sql_path(context))
        return steps

    def _build_answer(self, route: Dict[str, Any], steps: List[OrchestratorStep]) -> str:
        if not steps:
            return f"已路由到 {route['layer']}，但未提供足够上下文执行诊断。"
        summaries = [step.summary for step in steps if step.summary]
        return f"诊断路径：{route['layer']}。" + " ".join(summaries)

    def _infer_table(self, sql: str) -> str:
        import re

        match = re.search(r"\bFROM\s+([`\"\w]+)", sql, re.IGNORECASE)
        return match.group(1).strip("`\"") if match else "unknown"
