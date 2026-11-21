"""
FAISS vector index for MySQL Agent.
Supports IndexFlatIP (cosine similarity with normalized vectors).
"""
import json
import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict

from .document_loader import DocumentChunk
from .embedder import Embedder


class FAISSIndex:
    """FAISS index with metadata management."""
    
    def __init__(self, dimension: int, index_type: str = "flat_ip"):
        self.dimension = dimension
        self.index_type = index_type
        
        if index_type == "flat_ip":
            self.index = faiss.IndexFlatIP(dimension)
        elif index_type == "flat_l2":
            self.index = faiss.IndexFlatL2(dimension)
        elif index_type == "ivf_flat":
            # For larger datasets, IVF can be faster
            self.index = faiss.IndexIVFFlat(
                faiss.IndexFlatIP(dimension), dimension, 100
            )
        else:
            raise ValueError(f"Unknown index type: {index_type}")
        
        self.chunks: List[DocumentChunk] = []
        self._trained = False
    
    def add(self, chunks: List[DocumentChunk], embeddings: np.ndarray):
        """Add chunks and their embeddings to the index."""
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(f"Chunks count ({len(chunks)}) != embeddings count ({embeddings.shape[0]})")
        
        if embeddings.shape[1] != self.dimension:
            raise ValueError(f"Embedding dimension ({embeddings.shape[1]}) != index dimension ({self.dimension})")
        
        # Train IVF index if needed
        if self.index_type == "ivf_flat" and not self._trained:
            self.index.train(embeddings)
            self._trained = True
        
        self.index.add(embeddings)
        self.chunks.extend(chunks)
        print(f"✅ Added {len(chunks)} vectors. Total: {self.index.ntotal}")
    
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        filter_column: Optional[str] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for similar chunks.
        
        Returns:
            List of (chunk, score) tuples sorted by score descending
        """
        if self.index.ntotal == 0:
            return []
        
        # Ensure query is 2D
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        # Search more if filtering
        search_k = k * 3 if filter_column else k
        search_k = min(search_k, self.index.ntotal)
        
        scores, indices = self.index.search(query_embedding, search_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk = self.chunks[idx]
            
            # Apply column filter if specified
            if filter_column and chunk.source_column != filter_column:
                continue
            
            results.append((chunk, float(score)))
            if len(results) >= k:
                break
        
        return results
    
    def search_by_text(
        self,
        query: str,
        embedder: Embedder,
        k: int = 10,
        filter_column: Optional[str] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """Search by text query using embedder."""
        query_emb = embedder.encode_single(query)
        return self.search(query_emb, k=k, filter_column=filter_column)
    
    def save(self, path: str):
        """Save index and metadata to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save FAISS index
        faiss.write_index(self.index, str(path / "faiss_index.bin"))
        
        # Save chunks metadata
        with open(path / "chunks.jsonl", "w", encoding="utf-8") as f:
            for chunk in self.chunks:
                f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
        
        # Save index config
        config = {
            "dimension": self.dimension,
            "index_type": self.index_type,
            "total_vectors": self.index.ntotal,
            "total_chunks": len(self.chunks),
        }
        with open(path / "index_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Index saved to {path}")
    
    @classmethod
    def load(cls, path: str, embedder: Optional[Embedder] = None) -> "FAISSIndex":
        """Load index from disk."""
        path = Path(path)
        
        # Load index config
        with open(path / "index_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Create index instance
        index = cls(config["dimension"], config["index_type"])
        
        # Load FAISS index
        index.index = faiss.read_index(str(path / "faiss_index.bin"))
        
        # Load chunks
        with open(path / "chunks.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                index.chunks.append(DocumentChunk.from_dict(data))
        
        print(f"✅ Index loaded from {path}: {index.index.ntotal} vectors")
        return index
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        by_column = {}
        for chunk in self.chunks:
            col = chunk.source_column
            if col not in by_column:
                by_column[col] = 0
            by_column[col] += 1
        
        return {
            "total_vectors": self.index.ntotal,
            "total_chunks": len(self.chunks),
            "dimension": self.dimension,
            "index_type": self.index_type,
            "by_column": by_column,
        }
