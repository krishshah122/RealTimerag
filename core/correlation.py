"""Incident correlation and similar-incident detection."""

import hashlib
import re
from typing import Optional

from core.embeddings import EmbeddingModel
from core.incidents import IncidentManager


def _normalize_service(text: str, metadata: dict) -> str:
    service = metadata.get("service") or metadata.get("service_name")
    if service:
        return str(service).lower()
    # Heuristic: extract service-like tokens
    match = re.search(r"(\w+[-_]service|\w+[-_]api|db-\w+)", text.lower())
    return match.group(1) if match else "unknown"


def correlation_group_id(text: str, metadata: dict) -> str:
    """Derive a stable correlation group from service + error pattern."""
    service = _normalize_service(text, metadata)
    # Strip numbers/timestamps for pattern matching
    pattern = re.sub(r"\d+", "N", text.lower()[:200])
    key = f"{service}:{hashlib.md5(pattern.encode()).hexdigest()[:8]}"
    return f"CORR-{key}"


def find_correlated_incidents(incident_id: str) -> list[dict]:
    inc = IncidentManager.get(incident_id)
    if not inc:
        return []
    if inc.get("correlation_group"):
        return IncidentManager.get_correlation_group(inc["correlation_group"])
    return [inc]


def find_similar_incidents(
    text: str,
    vector_store,
    team: str | None = None,
    exclude_id: str | None = None,
    k: int = 5,
) -> list[dict]:
    """Semantic similarity search for 'have we seen this before?'"""
    results = vector_store.search(text, k=k * 3)
    similar = []
    for r in results:
        meta = r.get("metadata", {}) or {}
        if exclude_id and meta.get("issue_id") == exclude_id:
            continue
        if team and meta.get("team_tag") != team:
            continue
        similar.append({
            "issue_id": meta.get("issue_id"),
            "text": r["text"],
            "score": r["score"],
            "severity": meta.get("severity"),
            "status": meta.get("status"),
            "service": meta.get("service"),
            "timestamp": meta.get("timestamp"),
            "team_tag": meta.get("team_tag"),
            "recommendation": meta.get("recommendation"),
        })
        if len(similar) >= k:
            break
    return similar


def correlate_on_ingest(incident_id: str, text: str, metadata: dict) -> str:
    """Assign correlation group and link related incidents."""
    group = correlation_group_id(text, metadata)
    IncidentManager.set_correlation_group(incident_id, group)
    return group
