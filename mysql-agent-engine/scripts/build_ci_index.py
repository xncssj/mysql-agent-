#!/usr/bin/env python3
"""Build a tiny offline TF-IDF index for CI / L2 smoke (no GeekTime corpus required)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mysql_agent.vectorstore import DocumentLoader, Embedder, FAISSIndex

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "data/ci_knowledge/mysql45"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data/ci_vector_index"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CI mini vector index")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--output", "-o", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--tfidf-dim", type=int, default=16)
    parser.add_argument("--chunk-size", type=int, default=400)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    args = parser.parse_args()

    loader = DocumentLoader(
        sources={"mysql45": args.source},
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        min_chunk_length=20,
    )
    chunks = loader.load_all()
    if not chunks:
        raise SystemExit(f"no chunks loaded from {args.source}")

    texts = [c.content for c in chunks]
    # Small corpus: min_df=1 and clamp SVD dims below feature count.
    dim = max(2, min(args.tfidf_dim, max(len(texts) - 1, 2)))
    embedder = Embedder(
        use_tfidf=True,
        tfidf_config={
            "n_components": dim,
            "min_df": 1,
            "max_df": 1.0,
            "max_features": 5000,
        },
    )
    embedder.fit(texts)
    embeddings = embedder.encode(texts)

    index = FAISSIndex(dimension=embeddings.shape[1], index_type="flat_ip")
    index.add(chunks, embeddings)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    embedder.save(str(out))
    index.save(str(out))
    print(f"✅ CI index ready: {out} ({len(chunks)} chunks, dim={embeddings.shape[1]})")


if __name__ == "__main__":
    main()
