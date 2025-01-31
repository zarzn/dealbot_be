from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.models.notification import NotificationResponse, NotificationCreate, NotificationUpdate
from ....core.services.notification import NotificationService
from ....core.database import get_session
from ....core.auth import get_current_user
from ....core.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.post("", response_model=NotificationResponse)
async def create_notification(
    notification: NotificationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new notification"""
    try:
        notification_service = NotificationService(session)
        result = await notification_service.send_notification(
            user_id=current_user.id,
            title=notification.title,
            message=notification.message,
            notification_type=notification.type,
            data=notification.data,
            priority=notification.priority
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get user notifications"""
    try:
        notification_service = NotificationService(session)
        notifications = await notification_service.get_user_notifications(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            unread_only=unread_only
        )
        return notifications
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/unread/count", response_model=int)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get count of unread notifications"""
    try:
        notification_service = NotificationService(session)
        count = await notification_service.get_unread_count(current_user.id)
        return count
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/read", response_model=List[NotificationResponse])
async def mark_notifications_read(
    notification_ids: List[str],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Mark notifications as read"""
    try:
        notification_service = NotificationService(session)
        notifications = await notification_service.mark_as_read(
            notification_ids=notification_ids,
            user_id=current_user.id
        )
        return notifications
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("")
async def delete_notifications(
    notification_ids: List[str],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete notifications"""
    try:
        notification_service = NotificationService(session)
        await notification_service.delete_notifications(
            notification_ids=notification_ids,
            user_id=current_user.id
        )
        return {"status": "success", "message": "Notifications deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/all")
async def clear_all_notifications(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Clear all notifications"""
    try:
        notification_service = NotificationService(session)
        await notification_service.clear_all_notifications(current_user.id)
        return {"status": "success", "message": "All notifications cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/settings", response_model=dict)
async def get_notification_settings(
    current_user: User = Depends(get_current_user)
):
    """Get notification settings"""
    try:
        # Get user's notification preferences from their settings
        settings = current_user.notification_settings or {
            "email": True,
            "push": True,
            "sms": False,
            "deal_alerts": True,
            "price_drops": True,
            "goal_updates": True,
            "system_notifications": True
        }
        return settings
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/settings")
async def update_notification_settings(
    settings: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update notification settings"""
    try:
        # Update user's notification preferences
        current_user.notification_settings = settings
        session.add(current_user)
        await session.commit()
        return {"status": "success", "message": "Notification settings updated successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e)) 