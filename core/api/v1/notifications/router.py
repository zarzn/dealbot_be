"""Notification API router module."""

from typing import List, Dict, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.notification import (
    NotificationResponse,
    NotificationCreate,
    NotificationUpdate,
    NotificationType,
    NotificationPriority
)
from core.models.notification_preferences import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate
)
from core.services.notifications import NotificationService
from core.database import get_session
from core.dependencies import get_current_user
from core.models.user import User
from .websocket import handle_websocket

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications."""
    await handle_websocket(websocket)

@router.post(
    "",
    response_model=NotificationResponse,
    summary="Create a new notification"
)
async def create_notification(
    notification: NotificationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    background_tasks: BackgroundTasks = None
):
    """Create a new notification."""
    try:
        notification_service = NotificationService(session, background_tasks)
        result = await notification_service.create_notification(
            user_id=current_user.id,
            title=notification.title,
            message=notification.message,
            type=notification.type,
            channels=notification.channels,
            priority=notification.priority or NotificationPriority.MEDIUM,
            data=notification.data,
            notification_metadata=notification.metadata,
            action_url=notification.action_url,
            schedule_for=notification.schedule_for,
            deal_id=notification.deal_id,
            goal_id=notification.goal_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="Get user notifications"
)
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    notification_type: Optional[NotificationType] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    background_tasks: BackgroundTasks = None
):
    """Get notifications for the current user."""
    notification_service = NotificationService(session, background_tasks)
    return await notification_service.get_user_notifications(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        notification_type=notification_type
    )

@router.get(
    "/unread/count",
    response_model=int,
    summary="Get count of unread notifications"
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get count of unread notifications."""
    notification_service = NotificationService(session)
    return await notification_service.get_unread_count(current_user.id)

@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark notification as read"
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Mark a notification as read."""
    notification_service = NotificationService(session)
    notifications = await notification_service.mark_as_read(
        [str(notification_id)],
        str(current_user.id)
    )
    if not notifications:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notifications[0]

@router.put(
    "/read",
    response_model=List[NotificationResponse],
    summary="Mark multiple notifications as read"
)
async def mark_notifications_read(
    notification_ids: List[UUID],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Mark multiple notifications as read."""
    notification_service = NotificationService(session)
    return await notification_service.mark_as_read(
        [str(nid) for nid in notification_ids],
        str(current_user.id)
    )

@router.delete(
    "",
    summary="Delete notifications"
)
async def delete_notifications(
    notification_ids: List[UUID],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete notifications."""
    try:
        notification_service = NotificationService(session)
        await notification_service.delete_notifications(
            [str(nid) for nid in notification_ids],
            str(current_user.id)
        )
        return {"status": "success", "message": "Notifications deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/all",
    summary="Clear all notifications"
)
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Clear all notifications."""
    try:
        notification_service = NotificationService(session)
        await notification_service.clear_all_notifications(current_user.id)
        return {"status": "success", "message": "All notifications cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Get notification preferences"
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get notification preferences for the current user."""
    notification_service = NotificationService(session)
    return await notification_service.get_user_preferences(current_user.id)

@router.put(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences"
)
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update notification preferences for the current user."""
    notification_service = NotificationService(session)
    return await notification_service.update_preferences(
        current_user.id,
        preferences.dict(exclude_unset=True)
    ) 