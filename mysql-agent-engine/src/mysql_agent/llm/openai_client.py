"""OpenAI Function Calling adapter for ReAct orchestration."""
from __future__ import annotations

import json
import os
from typing import List, Optional


class OpenAILLMClient:
    """OpenAI chat completions with tool calling."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
    ):
        self.model = model
        self.temperature = temperature
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAILLMClient")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Install openai package: pip install openai") from exc

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self._client = OpenAI(**client_kwargs)

    def chat(self, messages: List[dict], tools: List[dict]) -> dict:
        api_messages = []
        for message in messages:
            if message.get("name") == "context":
                continue
            api_messages.append(self._convert_message(message))

        response = self._client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            tools=tools or None,
            temperature=self.temperature,
        )
        choice = response.choices[0]
        message = choice.message

        if message.tool_calls:
            return {
                "finish_reason": "tool_calls",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in message.tool_calls
                ],
            }

        return {
            "finish_reason": "stop",
            "content": message.content or "",
        }

    def complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        return response.choices[0].message.content or ""

    def _convert_message(self, message: dict) -> dict:
        role = message["role"]
        if role == "tool":
            return {
                "role": "tool",
                "tool_call_id": message["tool_call_id"],
                "content": message["content"],
            }
        converted = {"role": role, "content": message.get("content")}
        if message.get("tool_calls"):
            converted["tool_calls"] = message["tool_calls"]
        return converted
