from langsmith import traceable
@traceable(name="denseretriver")
class DenseRetriever:
    def __init__(self, vector_store):
        self.store = vector_store

    def search(self, query, k):
        return self.store.search(query, k)
