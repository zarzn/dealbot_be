"""Tests for notification system."""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket

from core.models.notification import (
    NotificationType,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    Notification
)
from core.services.notifications import NotificationService
from core.api.v1.notifications.websocket import NotificationManager, handle_websocket
from core.websockets.price_updates import PriceUpdateManager

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def notification_service(db):
    """Create notification service fixture."""
    return NotificationService(db)

@pytest.mark.asyncio
async def test_create_notification(notification_service, test_user):
    """Test creating a notification."""
    result = await notification_service.create_notification(
        user_id=test_user.id,
        title="Test Notification",
        message="This is a test notification",
        type=NotificationType.SYSTEM,
        channels=[NotificationChannel.IN_APP],
        priority=NotificationPriority.MEDIUM,
        data={
            "deal_id": str(uuid4()),
            "price": 99.99,
            "url": "https://example.com/deal"
        }
    )
    
    assert result.title == "Test Notification"
    assert result.message == "This is a test notification"
    assert result.type == NotificationType.SYSTEM
    assert NotificationChannel.IN_APP in result.channels
    assert result.status == NotificationStatus.PENDING

@pytest.mark.asyncio
async def test_get_notifications(notification_service, test_user):
    """Test getting user notifications."""
    # Create test notifications
    for i in range(3):
        await notification_service.create_notification(
            user_id=test_user.id,
            title=f"Test Notification {i}",
            message=f"Test message {i}",
            type=NotificationType.SYSTEM,
            channels=[NotificationChannel.IN_APP],
            priority=NotificationPriority.MEDIUM
        )
    
    notifications = await notification_service.get_user_notifications(test_user.id)
    assert len(notifications) == 3

@pytest.mark.asyncio
async def test_get_notifications_api(async_client: AsyncClient, auth_headers, test_user, notification_service):
    """Test getting user notifications via API."""
    # Create a test notification first
    await notification_service.create_notification(
        user_id=test_user.id,
        title="Test Notification",
        message="This is a test notification",
        type=NotificationType.SYSTEM,
        channels=[NotificationChannel.IN_APP],
        priority=NotificationPriority.MEDIUM
    )
    
    response = await async_client.get(
        "/api/v1/notifications",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["title"] == "Test Notification"

@pytest.mark.asyncio
async def test_get_unread_count(notification_service, test_user):
    """Test getting unread notification count."""
    # Create mix of read and unread notifications
    for i in range(5):
        notification = await notification_service.create_notification(
            user_id=test_user.id,
            title=f"Test Notification {i}",
            message=f"Test message {i}",
            type=NotificationType.SYSTEM,
            channels=[NotificationChannel.IN_APP],
            priority=NotificationPriority.MEDIUM
        )
    
    unread_count = await notification_service.get_unread_count(test_user.id)
    assert unread_count == 5

@pytest.mark.asyncio
async def test_delete_notifications(notification_service, test_user):
    """Test deleting notifications."""
    # Create test notifications
    notifications = []
    for i in range(3):
        notification = await notification_service.create_notification(
            user_id=test_user.id,
            title=f"Test Notification {i}",
            message=f"Test message {i}",
            type=NotificationType.SYSTEM,
            channels=[NotificationChannel.IN_APP],
            priority=NotificationPriority.MEDIUM
        )
        notifications.append(notification)
    
    # Delete notifications
    notification_ids = [notification.id for notification in notifications]
    await notification_service.delete_notifications(notification_ids, test_user.id)
    
    # Verify notifications are deleted
    remaining = await notification_service.get_user_notifications(test_user.id)
    assert len(remaining) == 0

@pytest.mark.asyncio
async def test_notification_preferences(notification_service, test_user):
    """Test notification preferences."""
    # Get default preferences
    preferences = await notification_service.get_user_preferences(test_user.id)
    assert preferences is not None
    assert NotificationChannel.IN_APP.value in preferences.enabled_channels
    
    # Update preferences
    update_data = {
        "enabled_channels": [NotificationChannel.EMAIL.value],
        "email_digest": True,
        "push_enabled": False,
        "do_not_disturb": True
    }
    
    updated_preferences = await notification_service.update_preferences(
        test_user.id,
        update_data
    )
    
    assert NotificationChannel.EMAIL.value in updated_preferences.enabled_channels
    assert updated_preferences.email_digest is True
    assert updated_preferences.push_enabled is False
    assert updated_preferences.do_not_disturb is True

@pytest.mark.asyncio
async def test_notification_preferences_api(async_client: AsyncClient, auth_headers):
    """Test updating notification preferences via API."""
    preferences = {
        "email_notifications": True,
        "push_notifications": False,
        "notification_frequency": "daily"
    }
    
    response = await async_client.put(
        "/api/v1/notifications/preferences",
        headers=auth_headers,
        json=preferences
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email_notifications"] is True
    assert data["push_notifications"] is False

@pytest.mark.asyncio
async def test_notification_delivery(notification_service, test_user, mocker):
    """Test notification delivery through different channels."""
    # Mock email service
    mock_email = mocker.patch("core.services.email.email_service.send_email")
    mock_email.return_value = True
    
    # Test in-app notification
    in_app_notification = await notification_service.create_notification(
        user_id=test_user.id,
        title="In-App Test",
        message="Test in-app notification",
        type=NotificationType.SYSTEM,
        channels=[NotificationChannel.IN_APP],
        priority=NotificationPriority.HIGH
    )
    assert in_app_notification is not None
    
    # Test email notification
    email_notification = await notification_service.create_notification(
        user_id=test_user.id,
        title="Email Test",
        message="Test email notification",
        type=NotificationType.SYSTEM,
        channels=[NotificationChannel.EMAIL],
        priority=NotificationPriority.HIGH
    )
    assert email_notification is not None
    assert mock_email.called

@pytest.mark.asyncio
async def test_websocket_notifications(async_client: AsyncClient, auth_headers, test_user, notification_service):
    """Test WebSocket notifications."""
    # Create a notification manager
    notification_manager = NotificationManager()
    
    # Simulate a WebSocket connection
    async def mock_websocket():
        return {
            "user_id": str(test_user.id),
            "send_json": lambda x: None
        }
    
    websocket = await mock_websocket()
    
    # Add connection
    await notification_manager.connect(websocket, str(test_user.id))
    
    # Send a test notification
    notification = await notification_service.create_notification(
        user_id=test_user.id,
        title="WebSocket Test",
        message="Test WebSocket notification",
        type=NotificationType.SYSTEM,
        channels=[NotificationChannel.IN_APP],
        priority=NotificationPriority.MEDIUM
    )
    
    # Verify the notification was sent
    assert notification is not None
    
    # Cleanup
    await notification_manager.disconnect(websocket)

@pytest.mark.asyncio
async def test_price_update_notifications(async_session: AsyncSession, test_user, test_deal, notification_service):
    """Test price update notifications."""
    price_update_manager = PriceUpdateManager()
    
    # Create a price tracker
    tracker = await price_update_manager.create_tracker(
        user_id=str(test_user.id),
        deal_id=str(test_deal.id),
        target_price=Decimal("89.99")
    )
    
    # Simulate a price update
    await price_update_manager.process_price_update(
        deal_id=str(test_deal.id),
        new_price=Decimal("89.99"),
        old_price=Decimal("99.99")
    )
    
    # Verify notification was sent
    notifications = await notification_service.get_user_notifications(test_user.id)
    assert len(notifications) > 0
    assert "price update" in notifications[0].message.lower() 