"""ReAct orchestrator for MySQL Agent."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .agent_bundle import AgentBundle
from .heuristic_llm import HeuristicLLMClient
from .tools import ToolRegistry, build_tool_registry


class LLMClient(Protocol):
    def chat(self, messages: List[dict], tools: List[dict]) -> dict:
        ...


@dataclass
class ReActStep:
    step: int
    tool: str
    args: Dict[str, Any]
    result_summary: str
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "tool": self.tool,
            "args": self.args,
            "result_summary": self.result_summary,
            "result": self.result,
        }


@dataclass
class ReActResult:
    query: str
    answer: str
    steps: List[ReActStep]
    total_steps: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "steps": [step.to_dict() for step in self.steps],
            "total_steps": self.total_steps,
        }


class ReActOrchestrator:
    """Reasoning + Acting loop that replaces fixed rule routing."""

    MAX_STEPS = 10

    SYSTEM_PROMPT = """你是 MySQL 智能运维 Agent。根据用户问题，选择合适的工具进行诊断。

可用工具已通过 Function Calling 注册。遵循以下策略：
1. 实例级问题 → 先 check_instance_metrics
2. SQL 问题 → explain_sql + suggest_index + rewrite_sql
3. 死锁 → analyze_deadlock
4. 复制 → check_replication
5. 需要知识 → search_knowledge

每次只调用一个工具，根据结果决定下一步。"""

    def __init__(
        self,
        bundle: AgentBundle,
        llm_client: Optional[LLMClient] = None,
        tools: Optional[ToolRegistry] = None,
    ):
        self.bundle = bundle
        self.llm = llm_client or HeuristicLLMClient()
        self.tools = tools or build_tool_registry(bundle)

    def run(self, user_query: str, context: Optional[Dict[str, Any]] = None) -> ReActResult:
        context = context or {}
        messages: List[dict] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "system", "name": "context", "content": json.dumps(context, ensure_ascii=False)},
            {"role": "user", "content": user_query},
        ]
        steps: List[ReActStep] = []

        for step_idx in range(self.MAX_STEPS):
            response = self.llm.chat(messages=messages, tools=self.tools.get_definitions())

            if response.get("finish_reason") == "stop":
                return ReActResult(
                    query=user_query,
                    answer=response.get("content") or "诊断完成。",
                    steps=steps,
                    total_steps=step_idx + 1,
                )

            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                return ReActResult(
                    query=user_query,
                    answer=response.get("content") or "未生成可执行工具调用。",
                    steps=steps,
                    total_steps=step_idx + 1,
                )

            for tool_call in tool_calls:
                fn_name = tool_call["function"]["name"]
                fn_args = json.loads(tool_call["function"]["arguments"])
                fn_args = self._merge_context_args(fn_name, fn_args, context)
                result = self.tools.execute(fn_name, fn_args)
                result_dict = self._normalize_result(result)
                summary = self._summarize_result(result_dict)

                steps.append(
                    ReActStep(
                        step=step_idx + 1,
                        tool=fn_name,
                        args=fn_args,
                        result_summary=summary,
                        result=result_dict,
                    )
                )

                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result_dict, ensure_ascii=False, default=str),
                    }
                )

        return ReActResult(
            query=user_query,
            answer="达到最大步数，请缩小问题范围。",
            steps=steps,
            total_steps=self.MAX_STEPS,
        )

    def _merge_context_args(
        self,
        tool_name: str,
        fn_args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(fn_args)
        if tool_name == "analyze_deadlock":
            if not merged.get("innodb_status") and context.get("innodb_status"):
                merged["innodb_status"] = context["innodb_status"]
            if not merged.get("innodb_status") and context.get("innodb_status_file"):
                from pathlib import Path

                merged["innodb_status"] = Path(context["innodb_status_file"]).read_text(
                    encoding="utf-8"
                )
        return merged

    def _normalize_result(self, result: Any) -> Dict[str, Any]:
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if isinstance(result, dict):
            return result
        return {"result": result}

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        if result.get("summary"):
            return str(result["summary"])
        if result.get("top_root_cause"):
            return f"Top root cause: {result['top_root_cause']}"
        if result.get("type"):
            return f"Deadlock type: {result['type']}"
        if result.get("anomalies"):
            return f"Detected {len(result['anomalies'])} anomalies"
        return str(result)[:500]
