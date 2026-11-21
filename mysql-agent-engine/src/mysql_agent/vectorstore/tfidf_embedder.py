"""
TF-IDF based embedder for offline use.
Uses sklearn's TfidfVectorizer + TruncatedSVD for dimensionality reduction.
"""
import pickle
import numpy as np
from pathlib import Path
from typing import List, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import Normalizer


class TFIDFEmbedder:
    """
    TF-IDF + SVD embedder for offline semantic search.
    Much faster to train and no external model downloads needed.
    """
    
    def __init__(
        self,
        n_components: int = 384,  # Match typical embedding dimensions
        max_features: int = 50000,
        ngram_range: tuple = (1, 2),
        min_df: int = 2,
        max_df: float = 0.95,
        random_state: int = 42,
    ):
        self.n_components = n_components
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.max_df = max_df
        self.random_state = random_state
        
        # Pipeline: TF-IDF -> SVD -> Normalize
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            min_df=min_df,
            max_df=max_df,
            sublinear_tf=True,
            strip_accents='unicode',
            analyzer='word',
            token_pattern=r'(?u)\b\w+\b|[\u4e00-\u9fff]',  # Support Chinese chars
        )
        self.svd = TruncatedSVD(
            n_components=n_components,
            random_state=random_state,
        )
        self.normalizer = Normalizer(copy=False)
        
        self.pipeline = make_pipeline(self.vectorizer, self.svd, self.normalizer)
        self._fitted = False
        self.dimension = n_components
    
    def fit(self, texts: List[str]):
        """Fit the TF-IDF + SVD pipeline on the corpus."""
        print(f"🔄 Fitting TF-IDF vectorizer on {len(texts)} documents...")
        self.pipeline.fit(texts)
        self._fitted = True
        explained = self.svd.explained_variance_ratio_.sum()
        print(f"✅ TF-IDF + SVD fitted. Explained variance: {explained:.2%}")
        print(f"   Vocabulary size: {len(self.vectorizer.vocabulary_)}")
        print(f"   Output dimension: {self.dimension}")
    
    def encode(
        self,
        texts: List[str],
        show_progress: bool = False,
        batch_size: Optional[int] = None,
    ) -> np.ndarray:
        """Transform texts to embeddings."""
        if not self._fitted:
            raise ValueError("Embedder not fitted. Call fit() first.")
        
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        
        # TF-IDF + SVD doesn't support batching easily, just transform all
        embeddings = self.pipeline.transform(texts).astype(np.float32)
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode a single text."""
        return self.encode([text])[0]
    
    def save(self, path: str):
        """Save the fitted pipeline to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        with open(path / "tfidf_pipeline.pkl", "wb") as f:
            pickle.dump(self.pipeline, f)
        
        # Save config
        import json
        config = {
            "n_components": self.n_components,
            "max_features": self.max_features,
            "ngram_range": self.ngram_range,
            "min_df": self.min_df,
            "max_df": self.max_df,
            "random_state": self.random_state,
            "dimension": self.dimension,
            "vocabulary_size": len(self.vectorizer.vocabulary_) if self._fitted else 0,
        }
        with open(path / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ TF-IDF embedder saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> "TFIDFEmbedder":
        """Load fitted pipeline from disk."""
        path = Path(path)
        
        with open(path / "tfidf_pipeline.pkl", "rb") as f:
            pipeline = pickle.load(f)
        
        import json
        with open(path / "config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        
        embedder = cls(
            n_components=config["n_components"],
            max_features=config["max_features"],
            ngram_range=tuple(config["ngram_range"]),
            min_df=config["min_df"],
            max_df=config["max_df"],
            random_state=config["random_state"],
        )
        embedder.pipeline = pipeline
        embedder._fitted = True
        embedder.dimension = config["dimension"]
        
        print(f"✅ TF-IDF embedder loaded from {path}")
        return embedder


# Quick test
if __name__ == "__main__":
    texts = [
        "MySQL 索引优化最佳实践",
        "如何优化慢查询 SQL 语句",
        "InnoDB Buffer Pool 配置调优",
        "死锁问题排查与解决方案",
        "主从复制延迟原因分析",
    ]
    
    embedder = TFIDFEmbedder(n_components=64)
    embedder.fit(texts)
    embs = embedder.encode(texts)
    print(f"Embeddings shape: {embs.shape}")
    print(f"Sample embedding: {embs[0][:5]}")
