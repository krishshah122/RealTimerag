"""Daily cleanup job: archive resolved incidents and purge expired vectors."""

from datetime import datetime

from config import RETENTION_DAYS_CLOSED, RETENTION_DAYS_RESOLVED
from core.analytics import AnalyticsManager
from core.incidents import IncidentManager
from core.vector_store import VectorStore


def run_cleanup() -> dict:
    """Archive old resolved incidents and remove expired vectors from index."""
    archived = IncidentManager.archive_resolved_older_than(RETENTION_DAYS_RESOLVED)

    expired_ids = IncidentManager.get_expired_incident_ids(RETENTION_DAYS_CLOSED)
    store = VectorStore()
    vectors_removed = 0
    analytics_removed = 0

    for issue_id in expired_ids:
        deleted = store.delete_documents(issue_id=issue_id)
        vectors_removed += deleted
        if AnalyticsManager.delete_issue(issue_id):
            analytics_removed += 1
        IncidentManager.delete_incident(issue_id)

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "archived_count": archived,
        "expired_purged": len(expired_ids),
        "vectors_removed": vectors_removed,
        "analytics_removed": analytics_removed,
    }
    print(f"Cleanup complete: {result}")
    return result
