"""Heuristic LLM client for ReAct orchestration without external APIs."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from .router import DiagnosisLayer, InputRouter


class HeuristicLLMClient:
    """Rule-driven planner that mimics an LLM tool-calling loop."""

    SQL_PIPELINE = ["explain_sql", "suggest_index", "rewrite_sql"]
    INSTANCE_PIPELINE = [
        "check_instance_metrics",
        "diagnose_root_cause",
        "cross_correlate",
        "generate_report",
    ]

    def __init__(self, router: Optional[InputRouter] = None):
        self.router = router or InputRouter()

    def chat(self, messages: List[dict], tools: List[dict]) -> dict:
        user_query = self._latest_user_message(messages)
        route = self.router.classify(user_query)
        called = self._called_tools(messages)
        available = {tool["function"]["name"] for tool in tools}
        context = self._extract_context(messages)

        next_tool = self._pick_next_tool(route["layer"], called, available, user_query, context)
        if next_tool is None:
            return {
                "finish_reason": "stop",
                "content": self._build_answer(route, called, messages),
            }

        tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
        return {
            "finish_reason": "tool_calls",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": next_tool,
                        "arguments": json.dumps(
                            self._build_tool_args(next_tool, user_query, context, messages),
                            ensure_ascii=False,
                        ),
                    },
                }
            ],
        }

    def _pick_next_tool(
        self,
        layer: str,
        called: set[str],
        available: set[str],
        user_query: str,
        context: Dict[str, Any],
    ) -> Optional[str]:
        if layer == DiagnosisLayer.SQL.value:
            for tool in self.SQL_PIPELINE:
                if tool in available and tool not in called:
                    return tool
            return None

        if layer == DiagnosisLayer.INSTANCE.value:
            for tool in self.INSTANCE_PIPELINE:
                if tool in available and tool not in called:
                    return tool
            return None

        if layer == DiagnosisLayer.ADVANCED.value:
            if re.search(r"死锁|deadlock", user_query, re.IGNORECASE):
                if "analyze_deadlock" in available and "analyze_deadlock" not in called:
                    return "analyze_deadlock"
                return None
            if "check_replication" in available and "check_replication" not in called:
                return "check_replication"
            return None

        if layer == DiagnosisLayer.KNOWLEDGE.value:
            if "search_knowledge" in available and "search_knowledge" not in called:
                return "search_knowledge"
            if "nl2sql" in available and "nl2sql" not in called:
                return "nl2sql"
            return None

        for tool in self.INSTANCE_PIPELINE + self.SQL_PIPELINE:
            if tool in available and tool not in called and self._has_context_for(tool, context):
                return tool
        if "search_knowledge" in available and "search_knowledge" not in called:
            return "search_knowledge"
        return None

    def _build_tool_args(
        self,
        tool_name: str,
        user_query: str,
        context: Dict[str, Any],
        messages: List[dict],
    ) -> Dict[str, Any]:
        if tool_name == "explain_sql":
            return {
                "sql": context.get("sql", self._extract_sql(user_query)),
                "explain": context.get("explain", {"type": "ALL", "rows": 1_000_000}),
            }
        if tool_name == "suggest_index":
            sql = context.get("sql", self._extract_sql(user_query))
            return {
                "sql": sql,
                "table": context.get("table", self._infer_table(sql)),
                "explain": context.get("explain", {"type": "ALL", "rows": 1_000_000}),
            }
        if tool_name == "rewrite_sql":
            return {"sql": context.get("sql", self._extract_sql(user_query))}
        if tool_name == "check_instance_metrics":
            return {"duration_minutes": context.get("duration_minutes", 60)}
        if tool_name == "diagnose_root_cause":
            anomalies = context.get("anomalies")
            if anomalies:
                return {"anomalies": anomalies}
            return {"anomalies": self._anomalies_from_messages(messages)}
        if tool_name == "cross_correlate":
            metrics = context.get("metrics")
            if metrics:
                return {"metrics": metrics}
            return {"metrics": self._metrics_from_messages(messages)}
        if tool_name == "analyze_deadlock":
            status = context.get("innodb_status")
            if status:
                return {"innodb_status": status}
            return {"innodb_status": ""}
        if tool_name == "check_replication":
            return {"slave_status": context.get("slave_status", {})}
        if tool_name == "search_knowledge":
            return {"query": user_query}
        if tool_name == "nl2sql":
            return {"question": user_query}
        if tool_name == "generate_report":
            diagnosis = self._diagnosis_from_messages(messages)
            return {
                "instance_id": context.get("instance_id", "mysql-instance-01"),
                "diagnosis_result": diagnosis,
            }
        return {}

    def _latest_user_message(self, messages: List[dict]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user" and message.get("content"):
                return str(message["content"])
        return ""

    def _extract_context(self, messages: List[dict]) -> Dict[str, Any]:
        for message in messages:
            if message.get("role") == "system" and message.get("name") == "context":
                return json.loads(message["content"])
        return {}

    def _called_tools(self, messages: List[dict]) -> set[str]:
        called: set[str] = set()
        for message in messages:
            for tool_call in message.get("tool_calls") or []:
                called.add(tool_call["function"]["name"])
        return called

    def _anomalies_from_messages(self, messages: List[dict]) -> List[dict]:
        for message in reversed(messages):
            if message.get("role") != "tool":
                continue
            try:
                payload = json.loads(message["content"])
            except json.JSONDecodeError:
                continue
            anomalies = payload.get("anomalies")
            if anomalies:
                return [
                    {"metric": item["metric"], "severity": item.get("severity", "WARNING")}
                    for item in anomalies
                ]
        return []

    def _metrics_from_messages(self, messages: List[dict]) -> Dict[str, List[float]]:
        for message in reversed(messages):
            if message.get("role") != "tool":
                continue
            try:
                payload = json.loads(message["content"])
            except json.JSONDecodeError:
                continue
            metrics = payload.get("metrics")
            if metrics:
                return metrics
        return {}

    def _diagnosis_from_messages(self, messages: List[dict]) -> Dict[str, Any]:
        diagnosis: Dict[str, Any] = {"anomalies": [], "root_causes": [], "steps": []}
        for message in messages:
            if message.get("role") != "tool":
                continue
            try:
                payload = json.loads(message["content"])
            except json.JSONDecodeError:
                continue
            if payload.get("anomalies"):
                diagnosis["anomalies"] = payload["anomalies"]
                diagnosis["summary"] = payload.get("summary", {})
                diagnosis["scan_time"] = payload.get("scan_time")
            if payload.get("root_causes"):
                diagnosis["root_causes"] = payload["root_causes"]
                diagnosis["top_root_cause"] = payload.get("top_root_cause")
                diagnosis["summary"] = payload.get("summary")
        return diagnosis

    def _has_context_for(self, tool_name: str, context: Dict[str, Any]) -> bool:
        if tool_name in {"explain_sql", "suggest_index", "rewrite_sql"}:
            return bool(context.get("sql"))
        if tool_name == "diagnose_root_cause":
            return bool(context.get("anomalies"))
        if tool_name == "cross_correlate":
            return bool(context.get("metrics"))
        if tool_name == "analyze_deadlock":
            return bool(context.get("innodb_status") or context.get("innodb_status_file"))
        if tool_name == "check_replication":
            return "slave_status" in context
        if tool_name == "check_instance_metrics":
            return True
        return False

    def _extract_sql(self, text: str) -> str:
        match = re.search(
            r"(select|insert|update|delete)\b.+",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        return match.group(0).strip() if match else "SELECT * FROM orders WHERE status = 1"

    def _infer_table(self, sql: str) -> str:
        match = re.search(r"\bFROM\s+([`\"\w]+)", sql, re.IGNORECASE)
        return match.group(1).strip("`\"") if match else "unknown"

    def _build_answer(self, route: Dict[str, Any], called: set[str], messages: List[dict]) -> str:
        summaries = []
        for message in messages:
            if message.get("role") != "tool":
                continue
            try:
                payload = json.loads(message["content"])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                if payload.get("summary"):
                    summaries.append(str(payload["summary"]))
                elif payload.get("top_root_cause"):
                    summaries.append(f"Top root cause: {payload['top_root_cause']}")
                elif payload.get("type"):
                    summaries.append(f"Deadlock type: {payload['type']}")

        if summaries:
            return f"诊断路径：{route['layer']}。" + " ".join(summaries)
        return f"诊断路径：{route['layer']}，已完成工具调用：{', '.join(sorted(called)) or '无'}。"
