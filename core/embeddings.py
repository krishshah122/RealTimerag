from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL
import threading
import logging

logging.basicConfig(level=logging.INFO)
from langsmith import traceable

class EmbeddingModel:
    _model = None
    _lock = threading.Lock()
   
    @classmethod
    @traceable(name="embeddingsload")
    def load(cls):
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    logging.info("🔥 Loading SentenceTransformer model (ONCE)...")
                    cls._model = SentenceTransformer(
                        EMBEDDING_MODEL,
                        local_files_only=True
                    )
                    logging.info("✅ SentenceTransformer model loaded")
        return cls._model
    
    @classmethod
    @traceable(name="embeddingsencode")
    def encode(cls, texts):
        model = cls.load()
        return model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
