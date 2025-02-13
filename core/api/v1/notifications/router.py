"""Notification API router module."""

from typing import List, Dict, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from core.models.notification import (
    NotificationResponse,
    NotificationCreate,
    NotificationUpdate,
    NotificationType,
    NotificationPriority,
    NotificationFilter,
    NotificationAnalytics
)
from core.models.notification_preferences import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate
)
from core.services.notifications import NotificationService
from core.database import get_async_db_session as get_db
from core.dependencies import get_current_user
from core.models.user import User, UserInDB
from core.api.v1.notifications.websocket import handle_websocket
from core.services.token import TokenService
from core.services.analytics import AnalyticsService
from core.api.v1.dependencies import (
    get_token_service,
    get_analytics_service
)

router = APIRouter(tags=["notifications"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications."""
    await handle_websocket(websocket)

@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="Get user notifications"
)
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    notification_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[NotificationResponse]:
    """Get user notifications with filtering."""
    try:
        notification_service = NotificationService(db)
        return await notification_service.get_user_notifications(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            unread_only=unread_only,
            notification_type=notification_type
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notifications: {str(e)}"
        )

@router.get(
    "/unread/count",
    response_model=int,
    summary="Get count of unread notifications"
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> int:
    """Get count of unread notifications."""
    notification_service = NotificationService(db)
    return await notification_service.get_unread_count(current_user.id)

@router.post(
    "",
    response_model=NotificationResponse,
    summary="Create a new notification"
)
async def create_notification(
    notification: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
) -> NotificationResponse:
    """Create a new notification."""
    try:
        notification_service = NotificationService(db)
        if background_tasks:
            notification_service.set_background_tasks(background_tasks)
        
        result = await notification_service.create_notification(
            user_id=current_user.id,
            title=notification.title,
            message=notification.message,
            type=notification.type,
            priority=notification.priority,
            metadata=notification.metadata
        )
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification: {str(e)}"
        )

@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark notification as read"
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> NotificationResponse:
    """Mark a notification as read."""
    notification_service = NotificationService(db)
    notifications = await notification_service.mark_as_read(
        [str(notification_id)],
        str(current_user.id)
    )
    if not notifications:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    return notifications[0]

@router.put(
    "/read",
    response_model=List[NotificationResponse],
    summary="Mark multiple notifications as read"
)
async def mark_notifications_read(
    notification_ids: List[UUID],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[NotificationResponse]:
    """Mark multiple notifications as read."""
    notification_service = NotificationService(db)
    return await notification_service.mark_as_read(
        [str(nid) for nid in notification_ids],
        str(current_user.id)
    )

@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notifications"
)
async def delete_notifications(
    notification_ids: List[UUID],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete notifications."""
    try:
        notification_service = NotificationService(db)
        await notification_service.delete_notifications(
            [str(nid) for nid in notification_ids],
            current_user.id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete(
    "/all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all notifications"
)
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Clear all notifications."""
    try:
        notification_service = NotificationService(db)
        await notification_service.clear_all_notifications(current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Get notification preferences"
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> NotificationPreferencesResponse:
    """Get notification preferences for the current user."""
    notification_service = NotificationService(db)
    return await notification_service.get_user_preferences(current_user.id)

@router.put(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update notification preferences"
)
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> NotificationPreferencesResponse:
    """Update notification preferences for the current user."""
    notification_service = NotificationService(db)
    return await notification_service.update_preferences(
        current_user.id,
        preferences.dict(exclude_unset=True)
    ) 