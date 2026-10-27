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
    _backend_type = None
    _lock = threading.Lock()

    @classmethod
    @traceable(name="embeddingsload")
    def load(cls):
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    # 1. Try fastembed (ONNX runtime: uses ~50MB RAM, perfect for Render 512MB free tier)
                    try:
                        from fastembed import TextEmbedding
                        logging.info("🔥 Loading fastembed model (ONNX Runtime: lightweight)...")
                        cls._model = TextEmbedding(model_name=EMBEDDING_MODEL)
                        cls._backend_type = "fastembed"
                        logging.info("✅ fastembed model loaded successfully")
                        return cls._model
                    except (ImportError, Exception) as fe_err:
                        logging.info("fastembed not available (%s), trying sentence-transformers...", fe_err)

                    # 2. Fallback to sentence_transformers (without memory-duplicating .half())
                    if EMBEDDING_MODEL:
                        try:
                            from sentence_transformers import SentenceTransformer
                            import gc
                            logging.info("🔥 Loading SentenceTransformer model...")
                            cls._model = SentenceTransformer(EMBEDDING_MODEL)
                            cls._backend_type = "sentence_transformers"
                            logging.info("✅ SentenceTransformer model loaded")
                            gc.collect()
                        except Exception as exc:
                            logging.warning("⚠️ sentence_transformers failed: %s — using pseudo-embeddings", exc)
                            cls._model = None
                            cls._backend_type = "pseudo"
                    else:
                        cls._model = None
                        cls._backend_type = "pseudo"
        return cls._model

    @classmethod
    @traceable(name="embeddingsencode")
    def encode(cls, texts):
        model = cls.load()
        if model is not None:
            if cls._backend_type == "fastembed":
                if isinstance(texts, str):
                    texts = [texts]
                embeddings = list(model.embed(texts))
                return np.array(embeddings, dtype=np.float32)
            else:
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
