from fastapi import APIRouter, Depends, HTTPException, status
from backend.core.models.notification import NotificationCreate, NotificationResponse
from backend.core.services.notification import NotificationService
from backend.core.auth.auth import get_current_user
from backend.core.dependencies import get_notification_service
from backend.core.models.user import User

router = APIRouter()

@router.post("/", response_model=NotificationResponse)
async def create_notification(
    notification: NotificationCreate,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service)
) -> NotificationResponse:
    """Create a new notification"""
    try:
        notification = await notification_service.create_notification(
            user_id=current_user.id,
            title=notification.title,
            message=notification.message,
            type=notification.type,
            channels=notification.channels,
            priority=notification.priority,
            data=notification.data,
            notification_metadata=notification.notification_metadata,
            action_url=notification.action_url,
            schedule_for=notification.schedule_for,
            deal_id=notification.deal_id,
            goal_id=notification.goal_id,
            expires_at=notification.expires_at
        )
        return NotificationResponse.from_orm(notification)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )