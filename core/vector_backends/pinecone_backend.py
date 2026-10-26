import json
import uuid

from config import (
    EMBEDDING_DIM,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE,
)
from core.embeddings import EmbeddingModel


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _pinecone_metadata(text: str, metadata: dict | None) -> dict:
    payload = {"text": text, **(metadata or {})}
    normalized = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            normalized[str(key)] = value
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            normalized[str(key)] = value
        else:
            normalized[str(key)] = json.dumps(value, ensure_ascii=False)
    return normalized


class PineconeBackend:
    def __init__(self):
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY must be set when VECTOR_BACKEND=pinecone")
        if not PINECONE_INDEX_NAME:
            raise ValueError(
                "PINECONE_INDEX_NAME must be set when VECTOR_BACKEND=pinecone"
            )

        from pinecone import Pinecone

        self.client = Pinecone(api_key=PINECONE_API_KEY)
        self.index = self.client.Index(PINECONE_INDEX_NAME)
        self.namespace = PINECONE_NAMESPACE
        self._validate_index()

    def _validate_index(self):
        description = self.client.describe_index(PINECONE_INDEX_NAME)
        dimension = _field(description, "dimension")
        if dimension is not None and dimension != EMBEDDING_DIM:
            raise ValueError(
                f"Pinecone index dimension is {dimension}, but EMBEDDING_DIM is "
                f"{EMBEDDING_DIM}; create an index with the configured dimension."
            )
        metric = _field(description, "metric")
        if metric is not None and metric != "cosine":
            raise ValueError(
                f"Pinecone index metric is {metric!r}; this application requires cosine."
            )

    def add_document(self, text: str, metadata: dict | None = None) -> str:
        values = EmbeddingModel.encode([text])[0].tolist()
        doc_metadata = metadata or {}
        document_id = str(doc_metadata.get("issue_id") or uuid.uuid4())
        self.index.upsert(
            vectors=[
                {
                    "id": document_id,
                    "values": values,
                    "metadata": _pinecone_metadata(text, doc_metadata),
                }
            ],
            namespace=self.namespace,
        )
        return document_id

    def search(
        self,
        query: str,
        k: int = 4,
        team_tag: str | None = None,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[dict]:
        query_filter = {}
        if team_tag:
            query_filter["team_tag"] = {"$eq": team_tag}
        if status:
            query_filter["status"] = {"$eq": status.upper()}
        if severity:
            query_filter["severity"] = {"$eq": severity.lower()}

        response = self.index.query(
            vector=EmbeddingModel.encode([query])[0].tolist(),
            top_k=k,
            namespace=self.namespace,
            include_metadata=True,
            **({"filter": query_filter} if query_filter else {}),
        )
        matches = _field(response, "matches", []) or []
        results = []
        for match in matches:
            metadata = dict(_field(match, "metadata", {}) or {})
            text = metadata.pop("text", "")
            results.append({
                "text": text,
                "score": float(_field(match, "score", 0.0) or 0.0),
                "metadata": metadata,
            })
        return results

    def delete_documents(self, *, issue_id=None, text=None, team_tag=None) -> int:
        matching_ids = []
        for document_id, document in self.all_docs().items():
            metadata = document.get("metadata", {}) or {}
            issue_match = issue_id and metadata.get("issue_id") == issue_id
            text_match = (
                text is not None
                and document.get("text") == text
                and (team_tag is None or metadata.get("team_tag") == team_tag)
            )
            if issue_match or text_match:
                matching_ids.append(document_id)

        if not matching_ids:
            return 0

        self.index.delete(ids=matching_ids, namespace=self.namespace)
        return len(matching_ids)

    def all_docs(self) -> dict:
        documents = {}
        for page in self.index.list(namespace=self.namespace, limit=100):
            listed_vectors = _field(page, "vectors", []) or []
            ids = [_field(vector, "id", vector) for vector in listed_vectors]
            if not ids:
                continue
            response = self.index.fetch(ids=ids, namespace=self.namespace)
            vectors = _field(response, "vectors", {}) or {}
            for document_id, vector in vectors.items():
                metadata = dict(_field(vector, "metadata", {}) or {})
                text = metadata.pop("text", "")
                documents[str(document_id)] = {"text": text, "metadata": metadata}
        return documents

    def count(self) -> int:
        stats = self.index.describe_index_stats()
        namespaces = _field(stats, "namespaces", {}) or {}
        namespace_stats = namespaces.get(self.namespace)
        if namespace_stats is None:
            return 0
        return int(_field(namespace_stats, "vector_count", 0) or 0)

    def reset(self):
        self.index.delete(delete_all=True, namespace=self.namespace)
