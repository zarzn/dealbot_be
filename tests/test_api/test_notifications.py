"""Test notification endpoints."""

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from typing import Dict, AsyncGenerator, Any
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from fastapi.testclient import TestClient
import json

from core.models.user import User
from core.models.notification import (
    Notification,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus
)
from core.services.notification import NotificationService
from core.services.email.backends.console import ConsoleEmailBackend
from core.exceptions.notification_exceptions import NotificationError
from core.config import settings

@pytest.fixture
async def notification_service(async_session: AsyncSession) -> NotificationService:
    """Create notification service fixture."""
    return NotificationService(async_session)

@pytest.fixture
def valid_notification_data() -> Dict[str, Any]:
    """Valid notification data for testing."""
    return {
        "title": "Test Notification",
        "message": "This is a test notification",
        "notification_type": NotificationType.SYSTEM,
        "priority": NotificationPriority.HIGH,
        "channels": [NotificationChannel.IN_APP],
        "notification_metadata": {"test": "data"}
    }

@pytest.mark.asyncio
async def test_create_notification(
    notification_service: NotificationService,
    test_user: User,
    valid_notification_data: Dict[str, Any]
):
    """Test creating a notification."""
    notification = await notification_service.create_notification(
        user_id=test_user.id,
        title=valid_notification_data["title"],
        message=valid_notification_data["message"],
        notification_type=valid_notification_data["notification_type"],
        priority=valid_notification_data["priority"],
        channels=valid_notification_data["channels"],
        notification_metadata=valid_notification_data["notification_metadata"]
    )
    
    assert notification.title == valid_notification_data["title"]
    assert notification.message == valid_notification_data["message"]
    assert notification.type == valid_notification_data["notification_type"].value
    assert notification.priority == valid_notification_data["priority"].value
    assert notification.notification_metadata == valid_notification_data["notification_metadata"]

@pytest.mark.asyncio
async def test_get_notifications(
    notification_service: NotificationService,
    test_user: User,
    valid_notification_data: Dict[str, Any]
):
    """Test getting notifications."""
    # Create test notifications
    await notification_service.create_notification(
        user_id=test_user.id,
        title=valid_notification_data["title"],
        message=valid_notification_data["message"],
        notification_type=valid_notification_data["notification_type"],
        priority=valid_notification_data["priority"],
        channels=valid_notification_data["channels"],
        notification_metadata=valid_notification_data["notification_metadata"]
    )
    
    notifications = await notification_service.get_notifications(user_id=test_user.id)
    assert len(notifications) > 0
    assert notifications[0].user_id == test_user.id

@pytest.mark.asyncio
async def test_get_notifications_api(
    async_client: AsyncClient,
    test_user: User,
    notification_service: NotificationService,
    valid_notification_data: Dict[str, Any],
    auth_headers: Dict[str, str],
    async_session: AsyncSession
):
    """Test getting notifications via API."""
    try:
        # Create a test notification first
        notification = await notification_service.create_notification(
            user_id=test_user.id,
            title=valid_notification_data["title"],
            message=valid_notification_data["message"],
            notification_type=valid_notification_data["notification_type"],
            priority=valid_notification_data["priority"],
            channels=valid_notification_data["channels"],
            notification_metadata=valid_notification_data["notification_metadata"]
        )
        await async_session.commit()
        
        response = await async_client.get("/api/v1/notifications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert str(notification.id) in [n["id"] for n in data]
    except Exception as e:
        await async_session.rollback()
        raise e

@pytest.mark.asyncio
async def test_get_unread_count(
    notification_service: NotificationService,
    test_user: User,
    valid_notification_data: Dict[str, Any]
):
    """Test getting unread notification count."""
    await notification_service.create_notification(
        user_id=test_user.id,
        title=valid_notification_data["title"],
        message=valid_notification_data["message"],
        notification_type=valid_notification_data["notification_type"],
        priority=valid_notification_data["priority"],
        channels=valid_notification_data["channels"],
        notification_metadata=valid_notification_data["notification_metadata"]
    )
    
    count = await notification_service.get_unread_count(user_id=test_user.id)
    assert count > 0

@pytest.mark.asyncio
async def test_delete_notifications(
    async_client: AsyncClient,
    test_user: User,
    notification_service: NotificationService,
    valid_notification_data: Dict[str, Any],
    auth_headers: Dict[str, str],
    async_session: AsyncSession
):
    """Test deleting notifications."""
    try:
        # Create a test notification first
        notification = await notification_service.create_notification(
            user_id=test_user.id,
            title=valid_notification_data["title"],
            message=valid_notification_data["message"],
            notification_type=valid_notification_data["notification_type"],
            priority=valid_notification_data["priority"],
            channels=valid_notification_data["channels"],
            notification_metadata=valid_notification_data["notification_metadata"]
        )
        await async_session.commit()
        
        # Send DELETE request with notification IDs as query parameters
        response = await async_client.delete(
            f"/api/v1/notifications?notification_ids={str(notification.id)}",
            headers=auth_headers
        )
        assert response.status_code == 204
    except Exception as e:
        await async_session.rollback()
        raise e

@pytest.mark.asyncio
async def test_notification_preferences(
    notification_service: NotificationService,
    test_user: User
):
    """Test notification preferences."""
    preferences = await notification_service.get_user_preferences(user_id=test_user.id)
    assert preferences is not None
    assert preferences.enabled_channels == [NotificationChannel.IN_APP, NotificationChannel.EMAIL]

@pytest.mark.asyncio
async def test_notification_preferences_api(
    async_client: AsyncClient,
    test_user: User,
    auth_headers: Dict[str, str],
    async_session: AsyncSession
):
    """Test getting notification preferences via API."""
    try:
        response = await async_client.get(
            "/api/v1/notifications/preferences",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert "enabled_channels" in data
    except Exception as e:
        await async_session.rollback()
        raise e

@pytest.mark.asyncio
async def test_notification_delivery(
    notification_service: NotificationService,
    test_user: User
):
    """Test notification delivery."""
    notification = await notification_service.create_notification(
        user_id=test_user.id,
        title="Test Delivery",
        message="Test notification delivery",
        notification_type=NotificationType.SYSTEM,
        priority=NotificationPriority.HIGH,
        channels=[NotificationChannel.IN_APP],
        notification_metadata={"test": "data"}
    )
    
    assert notification.status == NotificationStatus.PENDING.value
    assert notification.type == NotificationType.SYSTEM.value
    assert NotificationChannel.IN_APP.value in notification.channels

@pytest.mark.skip(reason="WebSocket implementation required")
@pytest.mark.asyncio
async def test_websocket_notifications(
    async_client: AsyncClient,
    test_user: User
):
    """Test WebSocket notifications."""
    pass

@pytest.mark.asyncio
async def test_price_update_notifications(
    notification_service: NotificationService,
    test_user: User
):
    """Test price update notifications."""
    notification = await notification_service.create_notification(
        user_id=test_user.id,
        title="Price Update",
        message="The price has changed",
        notification_type=NotificationType.PRICE_ALERT,
        priority=NotificationPriority.HIGH,
        channels=[NotificationChannel.IN_APP],
        notification_metadata={
            "old_price": 100.00,
            "new_price": 90.00,
            "product_id": "123"
        }
    )
    assert notification.type == NotificationType.PRICE_ALERT.value