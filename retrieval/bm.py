from threading import RLock
from time import monotonic

from rank_bm25 import BM25Okapi
from langsmith import traceable


SPARSE_INDEX_REFRESH_SECONDS = 30
_cache_lock = RLock()
_corpus_cache = {}


@traceable(name="sparseretriver")
class SparseRetriever:
    def __init__(self, documents):
        self.docs = documents
        if not documents:
            self.bm25 = None
        else:
            self.bm25 = BM25Okapi([d.split() for d in documents])

    def search(self, query, k):
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(query.split())
        ranked = sorted(
            zip(self.docs, scores),
            key=lambda x: x[1],
            reverse=True
        )
        return ranked[:k]


@traceable(name="cached_sparse_retriever")
def get_cached_sparse_retriever(vector_store, team=None):
    """Reuse a BM25 index until local writes or the refresh interval require a rebuild."""
    cache_key = vector_store.backend_name
    revision = vector_store.corpus_revision
    now = monotonic()

    with _cache_lock:
        cached = _corpus_cache.get(cache_key)
        if (
            cached is None
            or cached["revision"] != revision
            or now - cached["created_at"] >= SPARSE_INDEX_REFRESH_SECONDS
        ):
            documents = list(vector_store.iter_docs())
            metadata_by_team = {None: {}}
            for text, metadata in documents:
                metadata_by_team[None][text] = metadata
                team_tag = metadata.get("team_tag")
                if team_tag is not None:
                    metadata_by_team.setdefault(team_tag, {})[text] = metadata
            cached = {
                "revision": revision,
                "created_at": now,
                "documents": documents,
                "metadata_by_team": metadata_by_team,
                "retrievers": {},
            }
            _corpus_cache[cache_key] = cached

        retriever = cached["retrievers"].get(team)
        if retriever is None:
            texts = [
                text for text, metadata in cached["documents"]
                if team is None or metadata.get("team_tag") == team
            ]
            retriever = SparseRetriever(texts)
            cached["retrievers"][team] = retriever

        metadata_by_text = cached["metadata_by_team"].get(team, {})
        return retriever, metadata_by_text
