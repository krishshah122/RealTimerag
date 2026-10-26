"""Copy existing Qdrant incident documents into the configured Pinecone namespace."""

from core.vector_backends.pinecone_backend import PineconeBackend
from core.vector_backends.qdrant_backend import QdrantBackend


def migrate():
    source = QdrantBackend()
    destination = PineconeBackend()
    documents = source.all_docs()

    migrated = 0
    for document in documents.values():
        text = document.get("text", "")
        if not text:
            continue
        destination.add_document(text, document.get("metadata", {}) or {})
        migrated += 1

    print(
        f"Migrated {migrated} documents from Qdrant to Pinecone "
        f"namespace '{destination.namespace}'."
    )


if __name__ == "__main__":
    migrate()
