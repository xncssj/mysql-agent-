"""Hybrid dense + sparse retrieval."""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from .bm25 import BM25Retriever
from .document_loader import DocumentChunk
from .embedder import Embedder
from .faiss_index import FAISSIndex


class HybridSearcher:
    """Fuse dense FAISS scores with BM25 sparse scores."""

    def __init__(self, index: FAISSIndex, embedder: Embedder, alpha: float = 0.6):
        self.index = index
        self.embedder = embedder
        self.alpha = alpha
        documents = [f"{chunk.title} {chunk.content}" for chunk in index.chunks]
        self.bm25 = BM25Retriever(documents)

    def search(
        self,
        query: str,
        k: int = 10,
        filter_column: Optional[str] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        dense_results = self.index.search_by_text(query, self.embedder, k=k * 3, filter_column=filter_column)
        dense_scores = {id(chunk): score for chunk, score in dense_results}

        sparse_results = self.bm25.search(query, k=k * 3)
        sparse_scores = {idx: score for idx, score in sparse_results}

        if not dense_scores and not sparse_scores:
            return []

        dense_max = max(dense_scores.values()) if dense_scores else 1.0
        sparse_max = max(sparse_scores.values()) if sparse_scores else 1.0

        fused: dict[int, float] = {}
        for chunk, score in dense_results:
            idx = self.index.chunks.index(chunk)
            dense_norm = score / dense_max if dense_max else 0.0
            sparse_norm = sparse_scores.get(idx, 0.0) / sparse_max if sparse_max else 0.0
            fused[idx] = self.alpha * dense_norm + (1 - self.alpha) * sparse_norm

        for idx, score in sparse_results:
            if idx in fused:
                continue
            sparse_norm = score / sparse_max if sparse_max else 0.0
            fused[idx] = (1 - self.alpha) * sparse_norm

        ranked = sorted(fused.items(), key=lambda item: item[1], reverse=True)
        results: List[Tuple[DocumentChunk, float]] = []
        for idx, score in ranked:
            chunk = self.index.chunks[idx]
            if filter_column and chunk.source_column != filter_column:
                continue
            results.append((chunk, float(score)))
            if len(results) >= k:
                break
        return results
