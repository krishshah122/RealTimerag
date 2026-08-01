"""
One-time migration: copy FAISS/docs.json data into Qdrant.

Usage:
  VECTOR_BACKEND=qdrant python -m scripts.migrate_faiss_to_qdrant
"""

import json
import os

from core.embeddings import EmbeddingModel
from core.persistence import DOC_PATH
from core.vector_backends.qdrant_backend import QdrantBackend


def migrate():
    if not os.path.exists(DOC_PATH):
        print(f"No FAISS data found at {DOC_PATH}. Nothing to migrate.")
        return

    with open(DOC_PATH) as f:
        docs = json.load(f)

    if not docs:
        print("docs.json is empty. Nothing to migrate.")
        return

    backend = QdrantBackend()
    backend.reset()

    migrated = 0
    for doc_id, doc in docs.items():
        text = doc.get("text", "")
        metadata = doc.get("metadata", {}) or {}
        if not text:
            continue
        backend.add_document(text, metadata)
        migrated += 1

    print(f"Migrated {migrated} documents from FAISS → Qdrant collection '{backend.collection}'")


if __name__ == "__main__":
    migrate()
