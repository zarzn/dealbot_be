"""Admin API router for system administration tasks."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, get_async_db_context
from core.models.user import User
from core.dependencies import get_current_user
from core.notifications import TemplatedNotificationService
from core.services.user import UserService

router = APIRouter()

async def get_db_session():
    """Get DB session using the async context manager to prevent connection leaks."""
    async with get_async_db_context() as db:
        yield db

class MaintenanceScheduleRequest(BaseModel):
    """Request model for scheduling system maintenance."""
    start_date: datetime = Field(..., description="Start date and time of maintenance")
    end_date: datetime = Field(..., description="End date and time of maintenance")
    description: str = Field(..., description="Description of the maintenance work")
    affected_services: List[str] = Field(default_factory=list, description="List of affected services")
    severity: str = Field(default="medium", description="Severity of the maintenance impact (low, medium, high)")
    notify_users: bool = Field(default=True, description="Whether to notify all users")
    target_user_groups: Optional[List[str]] = Field(default=None, description="Specific user groups to target")

class MaintenanceScheduleResponse(BaseModel):
    """Response model for scheduled maintenance."""
    id: str
    start_date: datetime
    end_date: datetime
    description: str
    affected_services: List[str]
    severity: str
    notifications_sent: int
    scheduled_at: datetime
    scheduled_by: UUID

@router.post("/maintenance/schedule", response_model=MaintenanceScheduleResponse)
async def schedule_maintenance(
    maintenance: MaintenanceScheduleRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Schedule system maintenance and notify users.
    
    This endpoint requires admin privileges.
    It will create a system maintenance record and optionally notify all users or targeted user groups.
    """
    # Check if user has admin privileges
    if getattr(current_user, 'role', 'user') != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to schedule maintenance"
        )
    
    # Validate maintenance schedule
    if maintenance.start_date <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maintenance start date must be in the future"
        )
    
    if maintenance.end_date <= maintenance.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maintenance end date must be after start date"
        )
    
    # Function to send notifications in the background
    async def send_maintenance_notifications(
        maintenance_data: MaintenanceScheduleRequest,
        admin_id: UUID
    ):
        # Initialize notification service
        async with get_async_db_context() as session_db:
            notification_service = TemplatedNotificationService(session_db)
            user_service = UserService(session_db)
            
            # Format dates for notification
            start_date = maintenance_data.start_date.strftime("%B %d, %Y")
            start_time = maintenance_data.start_date.strftime("%H:%M %Z")
            end_time = maintenance_data.end_date.strftime("%H:%M %Z")
            
            # Determine which users to notify
            users_to_notify = []
            if maintenance_data.target_user_groups:
                # Get users in specific groups
                for group in maintenance_data.target_user_groups:
                    group_users = await user_service.get_users_by_group(group)
                    users_to_notify.extend(group_users)
            elif maintenance_data.notify_users:
                # Get all active users
                users_to_notify = await user_service.get_active_users()
            
            # Send notification to each user
            notifications_sent = 0
            for user in users_to_notify:
                try:
                    await notification_service.send_notification(
                        template_id="sys_maintenance",
                        user_id=user.id,
                        template_params={
                            "start_date": start_date,
                            "start_time": start_time,
                            "end_time": end_time,
                            "description": maintenance_data.description,
                            "affected_services": ", ".join(maintenance_data.affected_services),
                            "severity": maintenance_data.severity
                        },
                        metadata={
                            "maintenance_id": f"maint_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                            "scheduled_by": str(admin_id),
                            "affected_services": maintenance_data.affected_services,
                            "severity": maintenance_data.severity
                        }
                    )
                    notifications_sent += 1
                except Exception as e:
                    # Log error but continue with other users
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send maintenance notification to user {user.id}: {str(e)}")
            
            # Return the number of notifications sent
            return notifications_sent
    
    # Add the notification task to background tasks
    background_tasks.add_task(
        send_maintenance_notifications,
        maintenance_data=maintenance,
        admin_id=current_user.id
    )
    
    # Generate a unique ID for the maintenance schedule
    maintenance_id = f"maint_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Return the response
    return MaintenanceScheduleResponse(
        id=maintenance_id,
        start_date=maintenance.start_date,
        end_date=maintenance.end_date,
        description=maintenance.description,
        affected_services=maintenance.affected_services,
        severity=maintenance.severity,
        notifications_sent=0,  # This will be updated asynchronously
        scheduled_at=datetime.now(),
        scheduled_by=current_user.id
    ) 