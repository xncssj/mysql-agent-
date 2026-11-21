"""Simple A/B prompt experiment runner (no traffic split infra)."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ABVariant:
    name: str
    prompt_template: str
    weight: float = 1.0


@dataclass
class ABTrialResult:
    experiment: str
    variant: str
    input_hash: str
    score: float
    latency_ms: float
    meta: Dict[str, Any] = field(default_factory=dict)


class PromptABTest:
    """Assign variants deterministically by input hash; score via callback."""

    def __init__(self, name: str, variants: List[ABVariant], seed: str = "mysql-agent"):
        if not variants:
            raise ValueError("variants required")
        self.name = name
        self.variants = variants
        self.seed = seed
        self.results: List[ABTrialResult] = []

    def assign(self, payload: str) -> ABVariant:
        digest = hashlib.sha256(f"{self.seed}:{payload}".encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16)
        total = sum(max(v.weight, 0.0) for v in self.variants) or 1.0
        cursor = bucket % 10_000 / 10_000.0 * total
        acc = 0.0
        for variant in self.variants:
            acc += max(variant.weight, 0.0)
            if cursor <= acc:
                return variant
        return self.variants[-1]

    def run_once(
        self,
        payload: str,
        execute: Callable[[ABVariant, str], Any],
        score_fn: Callable[[Any], float],
    ) -> ABTrialResult:
        variant = self.assign(payload)
        started = time.perf_counter()
        output = execute(variant, payload)
        latency_ms = (time.perf_counter() - started) * 1000
        result = ABTrialResult(
            experiment=self.name,
            variant=variant.name,
            input_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12],
            score=float(score_fn(output)),
            latency_ms=round(latency_ms, 2),
            meta={"output_preview": str(output)[:200]},
        )
        self.results.append(result)
        return result

    def summary(self) -> Dict[str, Any]:
        by_variant: Dict[str, List[ABTrialResult]] = {}
        for item in self.results:
            by_variant.setdefault(item.variant, []).append(item)
        return {
            "experiment": self.name,
            "trials": len(self.results),
            "variants": {
                name: {
                    "n": len(items),
                    "avg_score": round(sum(i.score for i in items) / len(items), 4) if items else 0.0,
                    "avg_latency_ms": round(sum(i.latency_ms for i in items) / len(items), 2) if items else 0.0,
                }
                for name, items in by_variant.items()
            },
        }

    def dump_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for item in self.results:
                handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
