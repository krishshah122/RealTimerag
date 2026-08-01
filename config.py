import os

# Embeddings — BGE-small for production-inspired setup; falls back to MiniLM
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
TOP_K = int(os.getenv("TOP_K", "5"))
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

# Vector backend: "qdrant" (default) or "faiss" (local fallback)
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "qdrant").lower()
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "incidents")

# Recency windows (days) by severity
RECENCY_WINDOWS = {
    "critical": int(os.getenv("RECENCY_CRITICAL_DAYS", "90")),
    "high": int(os.getenv("RECENCY_HIGH_DAYS", "60")),
    "normal": int(os.getenv("RECENCY_NORMAL_DAYS", "30")),
    "low": int(os.getenv("RECENCY_LOW_DAYS", "30")),
    "medium": int(os.getenv("RECENCY_MEDIUM_DAYS", "30")),
}

# Retention / cleanup
RETENTION_DAYS_RESOLVED = int(os.getenv("RETENTION_DAYS_RESOLVED", "365"))
RETENTION_DAYS_CLOSED = int(os.getenv("RETENTION_DAYS_CLOSED", "180"))
CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))

# Notification channels
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_FROM_EMAIL = os.getenv("NOTIFY_FROM_EMAIL", "incidents@localhost")

# RBAC roles (ordered by privilege)
ROLES = ["analyst", "engineer", "sre", "team_lead", "admin"]
ROLE_ALIASES = {"user": "engineer", "viewer": "analyst"}
