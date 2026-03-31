"""Analytics API Endpoints"""

from fastapi import APIRouter, Query, Depends
from core.analytics import AnalyticsManager
from app.auth import get_current_user, UserContext

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/queries")
async def get_query_analytics(
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    """Get query analytics for last N hours"""
    return AnalyticsManager.get_query_stats(hours=hours)


@router.get("/issues")
async def get_issue_analytics(
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    """Get issue analytics for last N hours"""
    return AnalyticsManager.get_issue_stats(hours=hours)


@router.get("/timeline")
async def get_timeline(
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    """Get issue count over time"""
    return AnalyticsManager.get_time_series(hours=hours)


@router.get("/dashboard")
async def get_dashboard_data(
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
):
    """Get all analytics for dashboard"""
    return {
        "queries": AnalyticsManager.get_query_stats(hours=hours),
        "issues": AnalyticsManager.get_issue_stats(hours=hours),
        "timeline": AnalyticsManager.get_time_series(hours=hours),
    }
