"""Notification API endpoints."""

from fastapi import APIRouter, Depends

from app.auth import get_current_user, UserContext
from core.notifications import list_web_notifications, mark_notification_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(
    unread_only: bool = False,
    user: UserContext = Depends(get_current_user),
):
    return {"notifications": list_web_notifications(user.id, unread_only)}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: UserContext = Depends(get_current_user),
):
    ok = mark_notification_read(notification_id, user.id)
    return {"read": ok}
