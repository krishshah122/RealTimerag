from fastapi import APIRouter
from stream.producer import send_issue_event
from datetime import datetime

router = APIRouter()

@router.post("/log_issue")
def log_issue(issue: dict):
    event = {
        "type": issue.get("type", "unknown"),
        "text": issue["text"],
        "metadata": issue.get("metadata", {}),
        "timestamp": datetime.utcnow().isoformat()
    }

    send_issue_event(event)

    return {
        "status": "logged",
        "event": event
    }
