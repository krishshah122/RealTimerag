from fastapi import APIRouter, Depends, HTTPException
from stream.producer import send_issue_event
from datetime import datetime
from app.auth import get_current_user, UserContext
from core.analytics import AnalyticsManager
from core.vector_store import VectorStore
import uuid

router = APIRouter()


@router.post("/log_issue")
async def log_issue(issue: dict, user: UserContext = Depends(get_current_user)):
    """
    Log an incoming issue and tag it with the authenticated user's team.
    """
    team_tag = user.team
    issue_id = str(uuid.uuid4())[:8]

    event = {
        "id": issue_id,
        "type": issue.get("type", "unknown"),
        "text": issue["text"],
        "metadata": {
            "issue_id": issue_id,
            "issue_type": issue.get("type", "unknown"),
            "created_by_user_id": user.id,
            "created_by_email": user.email,
            "timestamp": datetime.utcnow().isoformat(),
            **issue.get("metadata", {}),
            **({"team_tag": team_tag} if team_tag else {}),
        },
        "team_tag": team_tag,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Always track in analytics DB (works even without Kafka)
    try:
        AnalyticsManager.track_issue(
            issue_id=issue_id,
            issue_type=event["type"],
            team=team_tag or "unassigned",
            text=event["text"],
            created_by_user_id=user.id,
            created_by_email=user.email,
        )
    except Exception as e:
        print(f"Analytics tracking failed (non-fatal): {e}")

    # Also send to Kafka stream (if available)
    try:
        send_issue_event(event)
    except Exception as e:
        print(f"Kafka send failed (non-fatal): {e}")

    return {
        "status": "logged",
        "event": event
    }


@router.get("/issues/mine")
async def list_my_issues(user: UserContext = Depends(get_current_user)):
    """Return issues created by the currently authenticated user."""
    return {
        "issues": AnalyticsManager.list_user_issues(user.id)
    }


@router.delete("/issues/{issue_id}")
async def delete_issue(issue_id: str, user: UserContext = Depends(get_current_user)):
    """
    Delete one specific issue from analytics and the vector store.

    For older indexed issues that do not have `issue_id` in document metadata,
    we fall back to matching by the analytics text and team.
    """
    issue = AnalyticsManager.get_issue(issue_id)
    if issue is None:
        return {
            "status": "not_found",
            "issue_id": issue_id,
            "message": "Issue not found"
        }

    if not issue.get("created_by_user_id"):
        raise HTTPException(status_code=409, detail="This older issue cannot be safely attributed to a specific user")
    if issue["created_by_user_id"] != user.id:
        raise HTTPException(status_code=403, detail="You can only delete issues you created")

    store = VectorStore()
    deleted_docs = store.delete_documents(
        issue_id=issue_id,
        text=issue.get("text"),
        team_tag=issue.get("team"),
    )
    analytics_deleted = AnalyticsManager.delete_issue(issue_id)

    return {
        "status": "deleted",
        "issue_id": issue_id,
        "deleted_from_vector_store": deleted_docs,
        "deleted_from_analytics": analytics_deleted,
    }
