"""
Text embedding for MySQL Agent.
Supports both TF-IDF (offline) and sentence-transformers (online).
"""
import numpy as np
from pathlib import Path
from typing import List, Optional

# Try to import sentence-transformers, fall back to TF-IDF
try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except ImportError:
    HAS_ST = False

from .tfidf_embedder import TFIDFEmbedder


DEFAULT_ST_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder:
    """Unified embedder supporting multiple backends."""
    
    def __init__(
        self,
        model_name: str = DEFAULT_ST_MODEL,
        device: Optional[str] = None,
        batch_size: int = 64,
        normalize: bool = True,
        use_tfidf: bool = False,
        tfidf_config: Optional[dict] = None,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.normalize = normalize
        self.use_tfidf = use_tfidf or not HAS_ST
        self._st_model = None
        self._tfidf_embedder = None
        
        if self.use_tfidf:
            tfidf_config = tfidf_config or {}
            self._tfidf_embedder = TFIDFEmbedder(**tfidf_config)
            self.dimension = self._tfidf_embedder.dimension
            print(f"🔄 Using TF-IDF embedder (dimension: {self.dimension})")
        else:
            print(f"🔄 Loading sentence-transformers model: {model_name}")
            self._st_model = SentenceTransformer(model_name, device=device)
            self.dimension = self._st_model.get_sentence_embedding_dimension()
            print(f"✅ Model loaded. Dimension: {self.dimension}")
    
    def fit(self, texts: List[str]):
        """Fit TF-IDF embedder if using TF-IDF backend."""
        if self.use_tfidf and self._tfidf_embedder:
            self._tfidf_embedder.fit(texts)
    
    def encode(
        self,
        texts: List[str],
        show_progress: bool = True,
        batch_size: Optional[int] = None,
    ) -> np.ndarray:
        """Encode texts to embeddings."""
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        
        if self.use_tfidf:
            if not self._tfidf_embedder._fitted:
                self.fit(texts)
            return self._tfidf_embedder.encode(texts, show_progress, batch_size)
        else:
            return self._encode_st(texts, show_progress, batch_size)
    
    def _encode_st(
        self,
        texts: List[str],
        show_progress: bool,
        batch_size: Optional[int],
    ) -> np.ndarray:
        """Encode using sentence-transformers."""
        bs = batch_size or self.batch_size
        all_embeddings = []
        
        # Process in batches
        iterator = range(0, len(texts), bs)
        if show_progress:
            from tqdm import tqdm
            iterator = tqdm(iterator, desc="Embedding", unit="batch")
        
        for i in iterator:
            batch = texts[i:i+bs]
            emb = self._st_model.encode(
                batch,
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            all_embeddings.append(emb)
        
        embeddings = np.vstack(all_embeddings).astype(np.float32)
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single text."""
        return self.encode([text])[0]
    
    def save(self, path: str):
        """Save model to local path."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        if self.use_tfidf and self._tfidf_embedder:
            self._tfidf_embedder.save(path)
        else:
            self._st_model.save(str(path / "st_model"))
        
        print(f"✅ Model saved to {path}")
    
    @classmethod
    def load(cls, path: str, **kwargs) -> "Embedder":
        """Load model from local path."""
        path = Path(path)
        
        # Check if TF-IDF model exists
        if (path / "tfidf_pipeline.pkl").exists():
            embedder = cls(use_tfidf=True)
            embedder._tfidf_embedder = TFIDFEmbedder.load(path)
            embedder.dimension = embedder._tfidf_embedder.dimension
            return embedder
        
        # Try sentence-transformers
        st_path = path / "st_model"
        if st_path.exists():
            return cls(model_name=str(st_path), **kwargs)
        
        raise FileNotFoundError(f"No valid model found in {path}")
