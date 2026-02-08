import faiss
import numpy as np
from core.embeddings import EmbeddingModel
from core.document_store import DocumentStore
from config import EMBEDDING_DIM
from core.persistence import load, save, current_version

from langsmith import traceable
@traceable(name="vecstore")
class VectorStore:
    def __init__(self):
        self._load_from_disk()

    def _load_from_disk(self):
        index, docs = load()

        if index is not None and docs is not None:
            self.index = index
            self.store = DocumentStore()
            self.store.docs = {int(k): v for k, v in docs.items()}
            self.store.counter = max(self.store.docs.keys(), default=-1) + 1
        else:
            self.index = faiss.IndexIDMap(
                faiss.IndexFlatIP(EMBEDDING_DIM)
            )
            self.store = DocumentStore()

        # 🔥 Track version
        self.version = current_version()

    def _reload_if_needed(self):
        latest = current_version()
        if latest != self.version:
            print("🔄 Reloading VectorStore from disk...")
            self._load_from_disk()

    def add_document(self, text, metadata=None):
        emb = EmbeddingModel.encode([text])
        faiss.normalize_L2(emb)

        doc_id = self.store.add(text, metadata)
        self.index.add_with_ids(emb, np.array([doc_id]))

        save(self.index, self.store.docs)

        # Update version after save
        self.version = current_version()
        return doc_id

    def search(self, query, k=4):
        # 🔥 Always ensure fresh data
        self._reload_if_needed()

        q_emb = EmbeddingModel.encode([query])
        faiss.normalize_L2(q_emb)

        scores, ids = self.index.search(q_emb, k)

        results = []
        for s, i in zip(scores[0], ids[0]):
            if i == -1:
                continue
            doc = self.store.get(int(i))
            results.append({
                "text": doc["text"],
                "score": float(s),
                "metadata": doc["metadata"]
            })
        return results
