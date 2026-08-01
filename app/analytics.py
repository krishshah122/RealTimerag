"""Analytics API Endpoints"""

from fastapi import APIRouter, Query, Depends
from core.analytics import AnalyticsManager
from core.incidents import IncidentManager
from app.auth import get_current_user, UserContext

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/queries")
async def get_query_analytics(
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    return AnalyticsManager.get_query_stats(hours=hours)


@router.get("/issues")
async def get_issue_analytics(
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    return AnalyticsManager.get_issue_stats(hours=hours)


@router.get("/timeline")
async def get_timeline(
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    return AnalyticsManager.get_time_series(hours=hours)


@router.get("/mttr")
async def get_mttr(
    hours: int = Query(168, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    return IncidentManager.get_mttr_stats(hours=hours)


@router.get("/severity")
async def get_severity_distribution(
    hours: int = Query(168, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    return {"distribution": IncidentManager.get_severity_distribution(hours=hours)}


@router.get("/services")
async def get_top_services(
    hours: int = Query(168, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    return {"top_services": IncidentManager.get_top_services(hours=hours)}


@router.get("/dashboard")
async def get_dashboard_data(
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    return {
        "queries": AnalyticsManager.get_query_stats(hours=hours),
        "issues": AnalyticsManager.get_issue_stats(hours=hours),
        "timeline": AnalyticsManager.get_time_series(hours=hours),
        "mttr": IncidentManager.get_mttr_stats(hours=hours),
        "severity_distribution": IncidentManager.get_severity_distribution(hours=hours),
        "top_services": IncidentManager.get_top_services(hours=hours),
    }
