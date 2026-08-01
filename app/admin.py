"""Admin and simulation API endpoints."""

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user, UserContext
from app.rbac import require_roles
from core.vector_store import VectorStore
from core.analytics import engine
from jobs.cleanup import run_cleanup
from simulation.alert_generator import generate_batch, generate_alert
from config import VECTOR_BACKEND

router = APIRouter(tags=["admin"])


@router.post("/admin/reset")
async def admin_reset(user: UserContext = Depends(require_roles("admin"))):
    """Reset vector store and analytics (admin only)."""
    from sqlalchemy import text

    store = VectorStore()
    store.reset()

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM query_analytics"))
        conn.execute(text("DELETE FROM issue_analytics"))
        conn.execute(text("DELETE FROM incidents"))
        conn.execute(text("DELETE FROM incident_timeline"))
        conn.execute(text("DELETE FROM web_notifications"))

    return {"status": "reset_complete", "vector_backend": VECTOR_BACKEND}


@router.post("/admin/cleanup")
async def trigger_cleanup(user: UserContext = Depends(require_roles("admin"))):
    return run_cleanup()


@router.get("/admin/vector-status")
async def vector_status(user: UserContext = Depends(require_roles("admin"))):
    """Check which vector backend is active and how many points are indexed."""
    store = VectorStore()
    return {
        "backend": VECTOR_BACKEND,
        "document_count": store.count(),
    }


@router.post("/simulation/generate")
async def generate_simulated_alerts(
    count: int = Query(10, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
):
    from app.issues import _ingest_issue

    alerts = generate_batch(count, team=user.team)
    results = []
    for alert in alerts:
        results.append(await _ingest_issue(alert, user))
    return {"generated": len(results), "incidents": results}


@router.post("/simulation/single")
async def generate_single_alert(user: UserContext = Depends(get_current_user)):
    from app.issues import _ingest_issue

    return await _ingest_issue(generate_alert(team=user.team), user)
