"""Recency weighting for time-aware retrieval."""

from datetime import datetime, timezone
from typing import Optional

from config import RECENCY_WINDOWS


def _parse_timestamp(ts: str | None) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def recency_window_days(severity: str | None) -> int:
    sev = (severity or "normal").lower()
    return RECENCY_WINDOWS.get(sev, RECENCY_WINDOWS.get("normal", 30))


def recency_score(timestamp: str | None, severity: str | None = None) -> float:
    """
    Exponential decay score in [0, 1]. Recent incidents score higher.
    Half-life is proportional to severity window.
    """
    dt = _parse_timestamp(timestamp)
    if dt is None:
        return 0.3

    age_days = (datetime.utcnow() - dt).total_seconds() / 86400
    window = recency_window_days(severity)
    if age_days > window:
        return 0.0

    half_life = max(window / 3, 1)
    import math
    return math.exp(-0.693 * age_days / half_life)


def within_recency_window(timestamp: str | None, severity: str | None = None) -> bool:
    dt = _parse_timestamp(timestamp)
    if dt is None:
        return True
    age_days = (datetime.utcnow() - dt).total_seconds() / 86400
    return age_days <= recency_window_days(severity)


def apply_recency_boost(
    docs: list[dict],
    semantic_weight: float = 0.5,
    bm25_weight: float = 0.3,
    recency_weight: float = 0.2,
) -> list[dict]:
    """Combine normalized scores with recency for final ranking."""
    if not docs:
        return []

    max_score = max((d.get("score", 0) for d in docs), default=1.0) or 1.0

    boosted = []
    for d in docs:
        meta = d.get("metadata", {}) or {}
        sem = d.get("score", 0) / max_score
        bm25 = d.get("bm25_score", 0)
        rec = recency_score(meta.get("timestamp"), meta.get("severity"))
        final = semantic_weight * sem + bm25_weight * bm25 + recency_weight * rec
        boosted.append({**d, "recency_score": rec, "final_score": final})

    boosted.sort(key=lambda x: x["final_score"], reverse=True)
    return boosted
