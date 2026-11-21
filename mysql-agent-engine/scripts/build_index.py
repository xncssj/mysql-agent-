#!/usr/bin/env python3
"""
Build vector index from three GeekTime MySQL columns.
Main entry point for index construction.
"""
import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mysql_agent.vectorstore import DocumentLoader, Embedder, FAISSIndex


# 默认输出到仓库内 data/vector_index；可用 --output 覆盖
DEFAULT_OUTPUT = str(Path(__file__).resolve().parent.parent / "data" / "vector_index")


def main():
    parser = argparse.ArgumentParser(description="Build MySQL Agent vector index")
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--model", "-m",
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        help="Embedding model name (ignored if using TF-IDF)"
    )
    parser.add_argument(
        "--use-tfidf", action="store_true", default=True,
        help="Use TF-IDF embedder (offline, no download needed)"
    )
    parser.add_argument(
        "--use-st", action="store_true",
        help="Force use sentence-transformers (requires internet)"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=800,
        help="Chunk size in characters"
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=150,
        help="Chunk overlap in characters"
    )
    parser.add_argument(
        "--columns", nargs="+",
        choices=["mysql45", "mysql_ops", "sql_master"],
        default=["mysql45", "mysql_ops", "sql_master"],
        help="Which columns to include"
    )
    parser.add_argument(
        "--index-type", choices=["flat_ip", "flat_l2", "ivf_flat"],
        default="flat_ip",
        help="FAISS index type"
    )
    parser.add_argument(
        "--tfidf-dim", type=int, default=384,
        help="TF-IDF SVD output dimension"
    )
    
    args = parser.parse_args()
    
    # Determine embedder type
    use_tfidf = args.use_tfidf and not args.use_st
    
    print("=" * 60)
    print("MySQL Agent - Vector Index Builder")
    print("=" * 60)
    print(f"Embedder: {'TF-IDF + SVD' if use_tfidf else 'Sentence-Transformers'}")
    
    # 1. Load documents
    print("\n📖 Step 1/4: Loading documents...")
    loader = DocumentLoader(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    all_chunks = loader.load_all()
    
    # Filter by selected columns
    if args.columns != ["mysql45", "mysql_ops", "sql_master"]:
        all_chunks = [c for c in all_chunks if c.source_column in args.columns]
    
    stats = loader.get_stats(all_chunks)
    print(f"✅ Loaded {stats['total_chunks']} chunks (~{stats['total_tokens']:,} tokens)")
    for col, col_stats in stats["by_column"].items():
        print(f"   - {col}: {col_stats['chunks']} chunks, ~{col_stats['tokens']:,} tokens")
    
    # 2. Create embeddings
    print("\n🔢 Step 2/4: Creating embeddings...")
    
    if use_tfidf:
        # TF-IDF embedder
        embedder = Embedder(
            use_tfidf=True,
            tfidf_config={"n_components": args.tfidf_dim},
        )
        texts = [c.content for c in all_chunks]
        embedder.fit(texts)
        embeddings = embedder.encode(texts)
    else:
        # Sentence-Transformers
        embedder = Embedder(model_name=args.model, use_tfidf=False)
        texts = [c.content for c in all_chunks]
        embeddings = embedder.encode(texts)
    
    # 3. Build FAISS index
    print("\n🏗️ Step 3/4: Building FAISS index...")
    index = FAISSIndex(dimension=embedder.dimension, index_type=args.index_type)
    index.add(all_chunks, embeddings)
    
    # 4. Save
    print("\n💾 Step 4/4: Saving index...")
    index.save(args.output)
    
    # Also save embedder
    embedder.save(args.output)
    
    # Print final stats
    final_stats = index.get_stats()
    print(f"\n📊 Final Index Stats:")
    print(f"   Total vectors: {final_stats['total_vectors']}")
    print(f"   Dimension: {final_stats['dimension']}")
    print(f"   Index type: {final_stats['index_type']}")
    for col, count in final_stats["by_column"].items():
        print(f"   - {col}: {count} chunks")
    
    print(f"\n✅ Done! Index saved to: {args.output}")


if __name__ == "__main__":
    main()
