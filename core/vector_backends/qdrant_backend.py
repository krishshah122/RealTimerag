"""Qdrant vector backend — default production store."""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from config import EMBEDDING_DIM, QDRANT_COLLECTION, QDRANT_HOST, QDRANT_PORT
from core.embeddings import EmbeddingModel

# Payload fields used for metadata filtering
INDEXED_PAYLOAD_FIELDS = ("team_tag", "issue_id", "status", "severity", "service")


class QdrantBackend:
    def __init__(self):
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)
        self.collection = QDRANT_COLLECTION
        self._ensure_collection()
        self._doc_counter = self._max_id() + 1

    def _ensure_collection(self):
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection not in collections:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(self):
        for field in INDEXED_PAYLOAD_FIELDS:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass  # index may already exist

    def _max_id(self) -> int:
        try:
            max_id = -1
            offset = None
            while True:
                points, offset = self.client.scroll(
                    collection_name=self.collection,
                    limit=256,
                    offset=offset,
                    with_vectors=False,
                    with_payload=False,
                )
                for p in points:
                    if str(p.id).isdigit():
                        max_id = max(max_id, int(p.id))
                if offset is None:
                    break
            return max_id
        except Exception:
            return -1

    def add_document(self, text: str, metadata: dict | None = None) -> int:
        doc_id = self._doc_counter
        self._doc_counter += 1
        emb = EmbeddingModel.encode([text])[0].tolist()
        payload = {"text": text, **(metadata or {})}
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=doc_id, vector=emb, payload=payload)],
        )
        return doc_id

    def delete_documents(self, *, issue_id=None, text=None, team_tag=None) -> int:
        ids_to_delete = []

        if issue_id:
            points, _ = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="issue_id", match=MatchValue(value=issue_id))]
                ),
                limit=100,
                with_vectors=False,
            )
            ids_to_delete.extend(p.id for p in points)

        if not ids_to_delete and text:
            points, _ = self.client.scroll(
                collection_name=self.collection,
                limit=10000,
                with_vectors=False,
            )
            for p in points:
                payload = p.payload or {}
                if payload.get("text") != text:
                    continue
                if team_tag and payload.get("team_tag") != team_tag:
                    continue
                ids_to_delete.append(p.id)

        if not ids_to_delete:
            return 0

        self.client.delete(collection_name=self.collection, points_selector=ids_to_delete)
        return len(ids_to_delete)

    def search(
        self,
        query: str,
        k: int = 4,
        team_tag: str | None = None,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[dict]:
        emb = EmbeddingModel.encode([query])[0].tolist()

        must = []
        if team_tag:
            must.append(FieldCondition(key="team_tag", match=MatchValue(value=team_tag)))
        if status:
            must.append(FieldCondition(key="status", match=MatchValue(value=status.upper())))
        if severity:
            must.append(FieldCondition(key="severity", match=MatchValue(value=severity.lower())))

        query_filter = Filter(must=must) if must else None

        results = self.client.query_points(
            collection_name=self.collection,
            query=emb,
            limit=k,
            query_filter=query_filter,
        )
        return [
            {
                "text": r.payload.get("text", ""),
                "score": float(r.score),
                "metadata": {key: val for key, val in r.payload.items() if key != "text"},
            }
            for r in results.points
        ]

    def all_docs(self) -> dict:
        docs = {}
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection,
                limit=256,
                offset=offset,
                with_vectors=False,
            )
            for p in points:
                payload = dict(p.payload or {})
                text = payload.pop("text", "")
                docs[int(p.id)] = {"text": text, "metadata": payload}
            if offset is None:
                break
        return docs

    def count(self) -> int:
        info = self.client.get_collection(self.collection)
        return info.points_count

    def reset(self):
        """Delete and recreate the collection."""
        try:
            self.client.delete_collection(self.collection)
        except Exception:
            pass
        self._ensure_collection()
        self._doc_counter = 0

    def reload(self):
        pass  # Qdrant is shared; no disk reload needed
