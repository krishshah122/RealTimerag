from langsmith import traceable
from threading import Lock

from config import VECTOR_BACKEND


_revision_lock = Lock()


def _create_backend():
    if VECTOR_BACKEND == "faiss":
        from core.vector_backends.faiss_backend import FaissBackend
        print("Using FAISS vector backend (fallback/local mode)")
        return FaissBackend()

    from core.vector_backends.qdrant_backend import QdrantBackend
    print("Using Qdrant vector backend")
    return QdrantBackend()


@traceable(name="vecstore")
class VectorStore:
    """Facade over Qdrant (default) or FAISS (optional fallback)."""

    _corpus_revision = 0

    def __init__(self):
        self._backend = _create_backend()

    @property
    def backend_name(self) -> str:
        return VECTOR_BACKEND

    @property
    def corpus_revision(self) -> int:
        with _revision_lock:
            return VectorStore._corpus_revision

    @staticmethod
    def _mark_corpus_changed() -> None:
        with _revision_lock:
            VectorStore._corpus_revision += 1

    @property
    def store(self):
        """Compatibility shim for code that reads store.docs."""
        if hasattr(self._backend, "store"):
            return self._backend.store

        class _PseudoStore:
            def __init__(self, docs):
                self.docs = docs

            def all_texts(self):
                return [v["text"] for v in self.docs.values()]

        return _PseudoStore(self._backend.all_docs())

    def iter_docs(self):
        """Yield (text, metadata) for all indexed documents."""
        for doc in self.store.docs.values():
            yield doc["text"], doc.get("metadata", {}) or {}

    def count(self) -> int:
        if hasattr(self._backend, "count"):
            return self._backend.count()
        return len(self.store.docs)

    def _reload_if_needed(self):
        if hasattr(self._backend, "reload"):
            self._backend.reload()

    def add_document(self, text, metadata=None):
        doc_id = self._backend.add_document(text, metadata)
        self._mark_corpus_changed()
        return doc_id

    def delete_documents(self, *, issue_id=None, text=None, team_tag=None):
        deleted = self._backend.delete_documents(
            issue_id=issue_id, text=text, team_tag=team_tag
        )
        if deleted:
            self._mark_corpus_changed()
        return deleted

    def search(self, query, k=4, team_tag=None, status=None, severity=None):
        self._reload_if_needed()
        if hasattr(self._backend, "search"):
            # Qdrant supports native metadata filters
            import inspect
            sig = inspect.signature(self._backend.search)
            if "status" in sig.parameters:
                return self._backend.search(
                    query, k=k, team_tag=team_tag, status=status, severity=severity
                )
        return self._backend.search(query, k=k, team_tag=team_tag)

    def reset(self):
        if hasattr(self._backend, "reset"):
            self._backend.reset()
            self._mark_corpus_changed()
