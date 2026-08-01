from config import EMBEDDING_MODEL
import threading
import logging
import hashlib
import numpy as np

logging.basicConfig(level=logging.INFO)
from langsmith import traceable


# Try to import SentenceTransformer; if unavailable (or torch missing),
# fall back to a lightweight deterministic pseudo-embedding for dev.
_HAS_ST = False
try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except Exception:
    SentenceTransformer = None


def _pseudo_embedding(text: str, dim: int = 512) -> np.ndarray:
    # Deterministic RNG seeded from text hash -> reproducible embeddings
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
    rng = np.random.RandomState(h % (2 ** 32))
    v = rng.rand(dim).astype("float32")
    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm
    return v


class EmbeddingModel:
    _model = None
    _lock = threading.Lock()

    @classmethod
    @traceable(name="embeddingsload")
    def load(cls):
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    if _HAS_ST and EMBEDDING_MODEL:
                        logging.info("🔥 Loading SentenceTransformer model (ONCE)...")
                        cls._model = SentenceTransformer(EMBEDDING_MODEL)
                        logging.info("✅ SentenceTransformer model loaded")
                    else:
                        logging.info(
                            "⚠️ sentence_transformers not available — using pseudo-embeddings"
                        )
                        cls._model = None
        return cls._model

    @classmethod
    @traceable(name="embeddingsencode")
    def encode(cls, texts):
        model = cls.load()
        if model is not None:
            return model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        # Fallback: deterministic pseudo-embeddings using numpy
        if isinstance(texts, str):
            texts = [texts]
        vecs = [_pseudo_embedding(t) for t in texts]
        return np.stack(vecs, axis=0)
