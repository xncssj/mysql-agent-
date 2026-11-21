"""L2 RAG Recall@k evaluation against rag_qa_set.jsonl."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..agents.rag_agent import MySQLRAGAgent

DEFAULT_QA_SET = (
    Path(__file__).resolve().parents[4]
    / "eval/rag_qa_set.jsonl"
)
DEFAULT_INDEX = DEFAULT_QA_SET.parent.parent / "data/vector_index"


def load_qa_set(path: str | Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _retrieved_ids(sources: List[Dict[str, Any]]) -> List[str]:
    return [str(src.get("chunk_id") or "") for src in sources]


def _text_blob(sources: List[Dict[str, Any]]) -> str:
    parts = []
    for src in sources:
        parts.append(
            " ".join(
                str(src.get(key, ""))
                for key in ("chunk_id", "title", "file", "snippet", "column")
            )
        )
    return " ".join(parts).lower()


def recall_at_k(
    item: Dict[str, Any],
    sources: List[Dict[str, Any]],
    k: int = 5,
) -> float:
    top = sources[:k]
    relevant_ids: Set[str] = set(item.get("relevant_doc_ids") or [])
    tokens = [t.lower() for t in item.get("source_contains") or []]

    if relevant_ids:
        retrieved = set(_retrieved_ids(top))
        hit = len(relevant_ids & retrieved)
        id_recall = hit / len(relevant_ids) if relevant_ids else 0.0
        if id_recall > 0 or not tokens:
            return id_recall

    # Soft labels (CI mini-index / weak supervision)
    if not tokens:
        return 1.0 if top else 0.0
    blob = _text_blob(top)
    hit = sum(1 for token in tokens if token in blob)
    return hit / len(tokens)


def run_rag_recall(
    qa_set_path: str | Path,
    index_path: str | Path,
    *,
    k: int = 5,
    min_recall: float = 0.8,
) -> Dict[str, Any]:
    agent = MySQLRAGAgent(str(index_path), top_k=k, quiet=True)
    items = load_qa_set(qa_set_path)
    scores: List[float] = []
    details: List[Dict[str, Any]] = []

    for item in items:
        result = agent.query(item["query"])
        score = recall_at_k(item, result.sources, k=k)
        scores.append(score)
        details.append(
            {
                "query": item["query"],
                "recall": round(score, 4),
                "retrieved_chunk_ids": _retrieved_ids(result.sources[:k]),
                "titles": [src.get("title") for src in result.sources[:k]],
            }
        )

    mean_recall = sum(scores) / len(scores) if scores else 0.0
    return {
        "qa_set": str(qa_set_path),
        "index_path": str(index_path),
        "k": k,
        "total": len(scores),
        "mean_recall": round(mean_recall, 4),
        "passed": mean_recall >= min_recall,
        "min_recall": min_recall,
        "details": details,
    }


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="L2 RAG Recall@k")
    parser.add_argument("--qa-set", default=str(DEFAULT_QA_SET))
    parser.add_argument("--index-path", default=str(DEFAULT_INDEX))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-recall", type=float, default=0.8)
    args = parser.parse_args(argv)

    index = Path(args.index_path)
    if not index.exists():
        print(json.dumps({"error": f"index not found: {index}"}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)

    report = run_rag_recall(args.qa_set, index, k=args.k, min_recall=args.min_recall)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
