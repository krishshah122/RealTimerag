from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL
class EmbeddingModel:
    _model = None

    @classmethod
    def encode(cls, texts):
        if cls._model is None:
            cls._model = SentenceTransformer(EMBEDDING_MODEL)
        return cls._model.encode(texts, normalize_embeddings=True)
