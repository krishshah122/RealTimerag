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

    def delete_documents(self, *, issue_id=None, text=None, team_tag=None):
        """
        Delete documents from the vector store.

        Prefer matching by `metadata.issue_id`. For older entries that do not
        persist the issue id in metadata, fall back to matching by `text` and
        optional `team_tag`.
        """
        self._reload_if_needed()

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
