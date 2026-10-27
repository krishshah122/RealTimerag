import asyncio
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from stream.producer import send_issue_event
from app.auth import get_current_user, UserContext
from app.rbac import can_access_team, has_role, require_roles
from core.analytics import AnalyticsManager
from core.vector_store import VectorStore
from core.incidents import IncidentManager, IncidentStatus
from core.correlation import correlate_on_ingest, find_similar_incidents, find_correlated_incidents
from core.notifications import notify_incident_created
from core.summarizer import summarize_incident

router = APIRouter()
logger = logging.getLogger(__name__)


class StatusTransition(BaseModel):
    status: str


class SummaryUpdate(BaseModel):
    summary: str | None = None
    root_cause: str | None = None
    impact: str | None = None
    recommendation: str | None = None


async def _summarize_issue_in_background(event: dict) -> None:
    issue_id = event["id"]
    try:
        summary_fields = await summarize_incident(
            event["text"], event.get("metadata", {})
        )
        await asyncio.to_thread(
            IncidentManager.update_summary, issue_id, **summary_fields
        )
        event["metadata"].update(summary_fields)
        await asyncio.to_thread(send_issue_event, event)
    except Exception:
        logger.exception(
            "Background incident summary or vector metadata update failed for %s",
            issue_id,
        )


def _notify_incident_in_background(
    incident: dict, user_id: str, user_email: str | None
) -> None:
    try:
        notify_incident_created(incident, user_id, user_email)
    except Exception:
        logger.exception(
            "Background incident notification failed for %s",
            incident.get("incident_id"),
        )


async def _ingest_issue(
    issue: dict, user: UserContext, background_tasks: BackgroundTasks
) -> dict:
    ingest_started = time.perf_counter()
    ingest_started_at = datetime.utcnow().isoformat()
    team_tag = user.team or "unassigned"
    issue_id = str(uuid.uuid4())[:8]
    metadata = issue.get("metadata", {}) or {}
    severity = metadata.get("severity", "medium")
    service = metadata.get("service")
    status = metadata.get("status", IncidentStatus.OPEN.value)

    # Create lifecycle record
    incident = await asyncio.to_thread(
        IncidentManager.create,
        incident_id=issue_id,
        text=issue["text"],
        team=team_tag,
        issue_type=issue.get("type", "alert"),
        severity=severity,
        service=service,
        created_by_user_id=user.id,
        created_by_email=user.email,
        metadata=metadata,
    )

    # Correlation
    group = await asyncio.to_thread(
        correlate_on_ingest,
        issue_id,
        issue["text"],
        {**metadata, "service": service},
    )
    incident["correlation_group"] = group

    # If status provided in metadata (simulation), apply transition
    if status != IncidentStatus.OPEN.value:
        try:
            await asyncio.to_thread(
                IncidentManager.transition_status,
                issue_id,
                status,
                user.id,
                user.email,
            )
            incident["status"] = status.upper()
        except ValueError:
            pass

    event = {
        "id": issue_id,
        "type": issue.get("type", "alert"),
        "text": issue["text"],
        "metadata": {
            "issue_id": issue_id,
            "incident_id": issue_id,
            "issue_type": issue.get("type", "alert"),
            "created_by_user_id": user.id,
            "created_by_email": user.email,
            "timestamp": datetime.utcnow().isoformat(),
            "ingest_started_at": ingest_started_at,
            "status": incident.get("status", IncidentStatus.OPEN.value),
            "severity": severity,
            "service": service,
            "correlation_group": group,
            "summary": incident.get("summary"),
            "root_cause": incident.get("root_cause"),
            "impact": incident.get("impact"),
            "recommendation": incident.get("recommendation"),
            **metadata,
            **({"team_tag": team_tag} if team_tag else {}),
        },
        "team_tag": team_tag,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        await asyncio.to_thread(
            AnalyticsManager.track_issue,
            issue_id=issue_id,
            issue_type=event["type"],
            team=team_tag,
            text=event["text"],
            created_by_user_id=user.id,
            created_by_email=user.email,
        )
    except Exception:
        logger.exception("Analytics tracking failed for incident %s", issue_id)

    try:
        publish_started = time.perf_counter()
        publish_result = {
            "status": "published",
            **await asyncio.to_thread(send_issue_event, event),
            "duration_ms": round((time.perf_counter() - publish_started) * 1000, 2),
        }
    except Exception:
        logger.exception("Kafka send failed for incident %s", issue_id)
        publish_result = {
            "status": "failed",
            "duration_ms": round((time.perf_counter() - publish_started) * 1000, 2),
        }

    background_tasks.add_task(
        _summarize_issue_in_background,
        event,
    )
    background_tasks.add_task(
        _notify_incident_in_background,
        incident,
        user.id,
        user.email,
    )

    return {
        "status": "logged",
        "event": event,
        "incident": incident,
        "kafka_publish": publish_result,
        "summary_status": "pending",
        "ingest_elapsed_ms": round((time.perf_counter() - ingest_started) * 1000, 2),
    }


@router.post("/log_issue")
async def log_issue(
    issue: dict,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user),
):
    return await _ingest_issue(issue, user, background_tasks)


@router.get("/issues/mine")
async def list_my_issues(user: UserContext = Depends(get_current_user)):
    return {"issues": AnalyticsManager.list_user_issues(user.id)}


@router.get("/incidents")
async def list_incidents(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    team: str | None = Query(None),
    hours: int | None = Query(168),
    user: UserContext = Depends(get_current_user),
):
    target_team = team or user.team
    if not can_access_team(user, target_team):
        raise HTTPException(403, "Access denied to this team's incidents")
    return {
        "incidents": IncidentManager.list_incidents(
            team=target_team, status=status, severity=severity, hours=hours
        )
    }


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, user: UserContext = Depends(get_current_user)):
    inc = IncidentManager.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    if not can_access_team(user, inc.get("team")):
        raise HTTPException(403, "Access denied")
    timeline = IncidentManager.get_timeline(incident_id)
    correlated = find_correlated_incidents(incident_id)
    return {"incident": inc, "timeline": timeline, "correlated": correlated}


@router.patch("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    body: StatusTransition,
    user: UserContext = Depends(get_current_user),
):
    inc = IncidentManager.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    if not can_access_team(user, inc.get("team")):
        raise HTTPException(403, "Access denied")
    try:
        updated = IncidentManager.transition_status(
            incident_id, body.status, user.id, user.email
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Update vector store metadata
    store = VectorStore()
    store.delete_documents(issue_id=incident_id)
    store.add_document(
        text=inc["text"],
        metadata={
            "issue_id": incident_id,
            "status": updated["status"],
            "severity": inc.get("severity"),
            "team_tag": inc.get("team"),
            "timestamp": inc.get("created_at"),
            "service": inc.get("service"),
            "summary": inc.get("summary"),
            "recommendation": inc.get("recommendation"),
        },
    )
    return {"incident": updated}


@router.patch("/incidents/{incident_id}/summary")
async def update_summary(
    incident_id: str,
    body: SummaryUpdate,
    user: UserContext = Depends(require_roles("sre", "team_lead", "admin")),
):
    inc = IncidentManager.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    updated = IncidentManager.update_summary(
        incident_id,
        summary=body.summary,
        root_cause=body.root_cause,
        impact=body.impact,
        recommendation=body.recommendation,
    )
    return {"incident": updated}


@router.get("/incidents/{incident_id}/similar")
async def similar_incidents(
    incident_id: str,
    k: int = Query(5, ge=1, le=20),
    user: UserContext = Depends(get_current_user),
):
    inc = IncidentManager.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    if not can_access_team(user, inc.get("team")):
        raise HTTPException(403, "Access denied")
    store = VectorStore()
    similar = find_similar_incidents(
        inc["text"], store, team=inc.get("team"), exclude_id=incident_id, k=k
    )
    return {"similar": similar}


@router.get("/incidents/{incident_id}/rca")
async def generate_incident_rca(
    incident_id: str,
    user: UserContext = Depends(get_current_user),
):
    from core.summarizer import generate_rca

    inc = IncidentManager.get(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    if not can_access_team(user, inc.get("team")):
        raise HTTPException(403, "Access denied")
    timeline = IncidentManager.get_timeline(incident_id)
    rca = await generate_rca(inc, timeline)
    return {"incident_id": incident_id, "rca": rca}


@router.delete("/issues/{issue_id}")
async def delete_issue(issue_id: str, user: UserContext = Depends(get_current_user)):
    issue = AnalyticsManager.get_issue(issue_id)
    if issue is None:
        return {"status": "not_found", "issue_id": issue_id}

    if not has_role(user, "admin"):
        if not issue.get("created_by_user_id"):
            raise HTTPException(409, "Cannot safely attribute this issue")
        if issue["created_by_user_id"] != user.id:
            raise HTTPException(403, "You can only delete your own issues")

    store = VectorStore()
    deleted_docs = store.delete_documents(
        issue_id=issue_id, text=issue.get("text"), team_tag=issue.get("team")
    )
    AnalyticsManager.delete_issue(issue_id)
    IncidentManager.delete_incident(issue_id)
    return {
        "status": "deleted",
        "issue_id": issue_id,
        "deleted_from_vector_store": deleted_docs,
    }
