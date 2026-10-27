"""Evaluate retrieval on a small, deterministic synthetic incident set.

Run from the rag directory with:
    python -m scripts.evaluate_retrieval

This exercises the configured embedding model and retrieval/ranking pipeline in
memory. It does not connect to Pinecone, Redpanda, or Groq.
"""

import os
import time
from datetime import datetime, timezone

os.environ.setdefault("GROQ_API_KEY", "synthetic-retrieval-evaluation")

import numpy as np

from agents.nodes import retrieve_node
from core.embeddings import EmbeddingModel


class InMemoryVectorStore:
    backend_name = "synthetic-retrieval-evaluation"
    corpus_revision = 1

    def __init__(self, documents):
        self.documents = documents
        self.vectors = EmbeddingModel.encode([doc["text"] for doc in documents])

    def iter_docs(self):
        return iter((doc["text"], doc["metadata"]) for doc in self.documents)

    def search(self, query, k=4, team_tag=None, status=None, severity=None):
        query_vector = EmbeddingModel.encode([query])[0]
        candidates = []
        for doc, vector in zip(self.documents, self.vectors):
            metadata = doc["metadata"]
            if team_tag and metadata.get("team_tag") != team_tag:
                continue
            if status and metadata.get("status", "OPEN") != status.upper():
                continue
            if severity and metadata.get("severity", "").lower() != severity.lower():
                continue
            score = float(np.dot(query_vector, vector))
            candidates.append(
                {"text": doc["text"], "score": score, "metadata": metadata}
            )
        return sorted(candidates, key=lambda doc: doc["score"], reverse=True)[:k]


def _synthetic_data():
    timestamp = datetime.now(timezone.utc).isoformat()
    incident_rows = [
        ("ops-db-pool", "Database connection pool exhausted during payment checkout, causing elevated HTTP 500 errors and checkout failures.", "ops", "critical"),
        ("ops-db-cpu", "CPU saturation on PostgreSQL caused query timeouts and delayed order processing.", "ops", "high"),
        ("ops-kafka-lag", "Kafka consumer lag increased after batch processor throughput fell, delaying alert indexing.", "ops", "high"),
        ("devops-image", "Kubernetes deployment failed due to an invalid image tag; pods entered ImagePullBackOff.", "devops", "high"),
        ("devops-redis", "Redis cache eviction caused elevated cache misses and API latency.", "devops", "medium"),
        ("security-ci-secret", "Credential leak in CI pipeline exposed cloud access keys, requiring immediate rotation.", "security", "critical"),
        ("security-auth", "Repeated authentication failures against admin endpoints came from a suspicious IP.", "security", "high"),
        ("ops-disk", "Disk capacity reached 100 percent on the metrics server, causing ingestion writes to fail.", "ops", "high"),
        ("ops-payment-provider", "Payment gateway timeouts followed increased latency from the external provider.", "ops", "critical"),
        ("devops-tls", "An expired TLS certificate on the internal ingress caused HTTPS requests to fail.", "devops", "high"),
        ("security-bucket", "Misconfigured object storage permissions exposed customer logs publicly.", "security", "critical"),
        ("ops-worker-memory", "A memory leak in the background worker caused OOM restarts and incomplete jobs.", "ops", "high"),
    ]
    documents = [
        {
            "text": text,
            "metadata": {
                "incident_id": incident_id,
                "team_tag": team,
                "severity": severity,
                "status": "OPEN",
                "timestamp": timestamp,
            },
        }
        for incident_id, text, team, severity in incident_rows
    ]
    queries = [
        {
            "query": "checkout failures because payment database connections ran out",
            "team": "ops",
            "relevant_ids": {"ops-db-pool"},
        },
        {
            "query": "Postgres CPU overload produced slow order queries",
            "team": "ops",
            "relevant_ids": {"ops-db-cpu"},
        },
        {
            "query": "alerts delayed because stream processor cannot keep up with Kafka",
            "team": "ops",
            "relevant_ids": {"ops-kafka-lag"},
        },
        {
            "query": "pods cannot launch after release due to bad container image reference",
            "team": "devops",
            "relevant_ids": {"devops-image"},
        },
        {
            "query": "cloud credentials exposed by build workflow and should be rotated",
            "team": "security",
            "relevant_ids": {"security-ci-secret"},
        },
        {
            "query": "background job restarts after memory exhaustion",
            "team": "ops",
            "relevant_ids": {"ops-worker-memory"},
        },
    ]
    return documents, queries


def _reciprocal_rank(retrieved_ids, relevant_ids):
    for rank, incident_id in enumerate(retrieved_ids, start=1):
        if incident_id in relevant_ids:
            return 1 / rank
    return 0.0


def main():
    documents, queries = _synthetic_data()
    store = InMemoryVectorStore(documents)
    id_by_text = {doc["text"]: doc["metadata"]["incident_id"] for doc in documents}
    latencies_ms = []
    recalls = []
    precisions = []
    reciprocal_ranks = []

    print(f"Synthetic corpus: {len(documents)} incidents; queries: {len(queries)}")
    print(f"Embedding model: {os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')}")
    print("Using in-memory vector search; no cloud writes or LLM generation.")

    for case_number, case in enumerate(queries, start=1):
        started = time.perf_counter()
        result = retrieve_node(
            {
                "query": case["query"],
                "team": case["team"],
            },
            store,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies_ms.append(elapsed_ms)
        retrieved_ids = [
            id_by_text[text] for text in result.get("docs", []) if text in id_by_text
        ]
        relevant_ids = case["relevant_ids"]
        hits = len(set(retrieved_ids) & relevant_ids)
        recalls.append(hits / len(relevant_ids))
        precisions.append(hits / max(len(retrieved_ids), 1))
        reciprocal_ranks.append(_reciprocal_rank(retrieved_ids, relevant_ids))
        print(
            f"{case_number}. team={case['team']} "
            f"Recall@3={recalls[-1]:.2f} "
            f"MRR@3={reciprocal_ranks[-1]:.2f} "
            f"latency={elapsed_ms:.1f} ms "
            f"retrieved={retrieved_ids}"
        )

    print("\nAggregate synthetic results")
    print(f"Recall@3:     {sum(recalls) / len(recalls):.3f}")
    print(f"Precision@3:  {sum(precisions) / len(precisions):.3f}")
    print(f"MRR@3:        {sum(reciprocal_ranks) / len(reciprocal_ranks):.3f}")
    print(f"Latency p50:  {float(np.percentile(latencies_ms, 50)):.1f} ms")
    print(f"Latency p95:  {float(np.percentile(latencies_ms, 95)):.1f} ms")
    print(
        "\nInterpretation: these are local synthetic retrieval measurements, "
        "not production or answer-quality benchmarks."
    )


if __name__ == "__main__":
    main()
