"""FAISS vector backend — optional local fallback (no Qdrant required)."""

import faiss
import numpy as np

from core.embeddings import EmbeddingModel
from core.document_store import DocumentStore
from core.persistence import load, save, current_version
from config import EMBEDDING_DIM


class FaissBackend:
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
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(EMBEDDING_DIM))
            self.store = DocumentStore()
        self.version = current_version()

    def reload(self):
        latest = current_version()
        if latest != self.version:
            print("Reloading FAISS backend from disk...")
            self._load_from_disk()

    def add_document(self, text: str, metadata: dict | None = None) -> int:
        emb = EmbeddingModel.encode([text])
        faiss.normalize_L2(emb)
        doc_id = self.store.add(text, metadata)
        self.index.add_with_ids(emb, np.array([doc_id]))
        save(self.index, self.store.docs)
        self.version = current_version()
        return doc_id

    def delete_documents(self, *, issue_id=None, text=None, team_tag=None) -> int:
        self.reload()
        ids_to_delete = []
        for doc_id, doc in self.store.docs.items():
            metadata = doc.get("metadata", {}) or {}
            issue_match = issue_id and metadata.get("issue_id") == issue_id
            fallback_match = (
                text is not None
                and doc.get("text") == text
                and (team_tag is None or metadata.get("team_tag") == team_tag)
            )
            if issue_match or fallback_match:
                ids_to_delete.append(int(doc_id))

        if not ids_to_delete:
            return 0

        self.index.remove_ids(np.array(ids_to_delete, dtype="int64"))
        for doc_id in ids_to_delete:
            self.store.docs.pop(doc_id, None)
        save(self.index, self.store.docs)
        self.version = current_version()
        return len(ids_to_delete)

    def search(self, query: str, k: int = 4, team_tag: str | None = None, **_) -> list[dict]:
        self.reload()
        q_emb = EmbeddingModel.encode([query])
        faiss.normalize_L2(q_emb)
        scores, ids = self.index.search(q_emb, k * 3 if team_tag else k)

        results = []
        for s, i in zip(scores[0], ids[0]):
            if i == -1:
                continue
            doc = self.store.get(int(i))
            meta = doc.get("metadata", {}) or {}
            if team_tag and meta.get("team_tag") != team_tag:
                continue
            results.append({"text": doc["text"], "score": float(s), "metadata": meta})
            if len(results) >= k:
                break
        return results

    def all_docs(self) -> dict:
        self.reload()
        return dict(self.store.docs)

    def count(self) -> int:
        return len(self.store.docs)

    def reset(self):
        self.index = faiss.IndexIDMap(faiss.IndexFlatIP(EMBEDDING_DIM))
        self.store = DocumentStore()
        save(self.index, self.store.docs)
        self.version = current_version()
