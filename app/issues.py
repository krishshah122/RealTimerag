from fastapi import APIRouter, Depends
from stream.producer import send_issue_event
from datetime import datetime
from app.auth import get_current_user, UserContext

router = APIRouter()


@router.post("/log_issue")
def log_issue(issue: dict, user: UserContext = Depends(get_current_user)):
    """
    Log an incoming issue and tag it with the authenticated user's team.
    """
    team_tag = user.team

    event = {
        "type": issue.get("type", "unknown"),
        "text": issue["text"],
        "metadata": {
            **issue.get("metadata", {}),
            **({"team_tag": team_tag} if team_tag else {}),
        },
        "team_tag": team_tag,
        "timestamp": datetime.utcnow().isoformat()
    }

    send_issue_event(event)

    return {
        "status": "logged",
        "event": event
    }
