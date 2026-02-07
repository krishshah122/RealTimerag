from rank_bm25 import BM25Okapi

class SparseRetriever:
    def __init__(self, documents):
        self.docs = documents
        if not documents:
            self.bm25 = None
        else:
            self.bm25 = BM25Okapi([d.split() for d in documents])

    def search(self, query, k):
        if self.bm25 is None:
            return []   # <- prevent crash 
        scores = self.bm25.get_scores(query.split())
        ranked = sorted(
            zip(self.docs, scores),
            key=lambda x: x[1],
            reverse=True
        )
        return ranked[:k]
