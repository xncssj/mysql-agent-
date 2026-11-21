"""BM25 sparse retrieval."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Sequence, Tuple


def _tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    for word in re.findall(r"[\u4e00-\u9fff]+|\w+", text.lower()):
        tokens.append(word)
        if re.fullmatch(r"[\u4e00-\u9fff]+", word) and len(word) > 1:
            tokens.extend(list(word))
    return tokens


class BM25Retriever:
    """Lightweight BM25 retriever for hybrid search."""

    def __init__(self, documents: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self._tokenized = [_tokenize(doc) for doc in self.documents]
        self._doc_freq: Counter[str] = Counter()
        for tokens in self._tokenized:
            self._doc_freq.update(set(tokens))
        self._avgdl = sum(len(tokens) for tokens in self._tokenized) / max(len(self._tokenized), 1)
        self._n_docs = len(self.documents)

    def score(self, query: str) -> List[float]:
        query_tokens = _tokenize(query)
        scores = [0.0] * self._n_docs
        for token in query_tokens:
            df = self._doc_freq.get(token, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self._n_docs - df + 0.5) / (df + 0.5))
            for idx, tokens in enumerate(self._tokenized):
                tf = tokens.count(token)
                if tf == 0:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * len(tokens) / self._avgdl)
                scores[idx] += idf * (tf * (self.k1 + 1)) / denom
        return scores

    def search(self, query: str, k: int = 10) -> List[Tuple[int, float]]:
        scores = self.score(query)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        return [(idx, score) for idx, score in ranked[:k] if score > 0]
