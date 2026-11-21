"""LLM client protocol."""
from __future__ import annotations

from typing import List, Protocol


class LLMClient(Protocol):
    def chat(self, messages: List[dict], tools: List[dict]) -> dict:
        ...
