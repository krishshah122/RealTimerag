from config import EMBEDDING_MODEL
import threading
import logging
import hashlib
import numpy as np

logging.basicConfig(level=logging.INFO)
from langsmith import traceable


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
                    if EMBEDDING_MODEL:
                        try:
                            from sentence_transformers import SentenceTransformer
                        except ImportError as exc:
                            raise RuntimeError(
                                "sentence-transformers is required when "
                                "EMBEDDING_MODEL is configured."
                            ) from exc
                        import torch, gc
                        # Minimize memory: single thread, no grad tracking
                        torch.set_num_threads(1)
                        torch.set_grad_enabled(False)
                        logging.info("🔥 Loading SentenceTransformer model (ONCE)...")
                        cls._model = SentenceTransformer(EMBEDDING_MODEL)
                        # Switch to half-precision to halve model memory
                        cls._model.half()
                        logging.info("✅ SentenceTransformer model loaded (half-precision)")
                        gc.collect()
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
