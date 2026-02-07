class DocumentStore:
    def __init__(self):
        self.docs = {}
        self.counter = 0

    def add(self, text, metadata=None):
        doc_id = self.counter
        self.docs[doc_id] = {
            "text": text,
            "metadata": metadata or {}
        }
        self.counter += 1
        return doc_id

    def get(self, doc_id):
        return self.docs[doc_id]

    def all_texts(self):
        return [v["text"] for v in self.docs.values()]
    
    def all(self):
        return self.docs

