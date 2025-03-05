"""Tests for Notification Service.

This module contains tests for the NotificationService class, which handles notifications
of various types across multiple channels.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4, UUID
import json

from core.services.notification import (
    NotificationService,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus
)
from core.models.notification import Notification, NotificationResponse
from core.models.user_preferences import UserPreferences, NotificationFrequency, NotificationTimeWindow
from core.exceptions import (
    NotificationError,
    NotificationNotFoundError,
    NotificationDeliveryError
)
from backend.backend_tests.utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def mock_db_session():
    """Create a mock database session."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    return mock_session

@pytest.fixture
async def mock_redis_client():
    """Create a mock Redis client."""
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock(return_value=True)
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.incr = AsyncMock(return_value=1)
    return mock_redis

@pytest.fixture
async def notification_service(mock_db_session, mock_redis_client):
    """Create a notification service with mock dependencies."""
    with patch("core.services.notification.RedisClient", return_value=mock_redis_client):
        service = NotificationService(session=mock_db_session)
        return service

@pytest.fixture
def sample_notification():
    """Create a sample notification for testing."""
    return Notification(
        id=uuid4(),
        user_id=uuid4(),
        title="Test Notification",
        message="This is a test notification",
        type=NotificationType.SYSTEM.value,
        channels=[NotificationChannel.IN_APP.value],
        priority=NotificationPriority.MEDIUM.value,
        status=NotificationStatus.PENDING.value,
        created_at=datetime.utcnow(),
        metadata={"test": True}
    )

@pytest.fixture
def sample_user_preferences():
    """Create sample user preferences for testing."""
    return UserPreferences(
        id=uuid4(),
        user_id=uuid4(),
        enabled_channels=[
            NotificationChannel.IN_APP.value,
            NotificationChannel.EMAIL.value
        ],
        notification_frequency={
            NotificationType.SYSTEM.value: {"type": NotificationType.SYSTEM.value, "frequency": NotificationFrequency.IMMEDIATE.value},
            NotificationType.DEAL.value: {"type": NotificationType.DEAL.value, "frequency": NotificationFrequency.DAILY.value}
        },
        time_windows={
            NotificationChannel.IN_APP.value: {"start_time": "08:00", "end_time": "20:00", "timezone": "UTC"},
            NotificationChannel.EMAIL.value: {"start_time": "09:00", "end_time": "18:00", "timezone": "UTC"}
        },
        do_not_disturb=False,
        email_digest=True,
        minimum_priority=NotificationPriority.LOW.value
    )

@service_test
async def test_create_notification(notification_service, mock_db_session, mock_redis_client):
    """Test creating a notification."""
    # Setup
    user_id = uuid4()
    title = "Test Notification"
    message = "This is a test notification"
    notification_type = NotificationType.SYSTEM
    channels = [NotificationChannel.IN_APP]
    metadata = {"test": True}
    
    # Mock the session execute method to return a user
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = MagicMock(
        id=user_id,
        email="test@example.com"
    )
    
    # Create a mock notification
    mock_notification = MagicMock(
        id=uuid4(),
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type.value,
        channels=[channel.value for channel in channels],
        priority=NotificationPriority.MEDIUM.value,
        metadata=metadata,
        created_at=datetime.utcnow(),
        status=NotificationStatus.PENDING.value
    )
    
    # Make execute().scalars().first() return the mock notification after "committing"
    def side_effect(*args, **kwargs):
        result = AsyncMock()
        result.scalar_one.return_value = mock_notification
        return result
        
    mock_db_session.execute.side_effect = side_effect
    
    # Mock the _cache_notification method
    notification_service._cache_notification = AsyncMock()
    
    # Execute
    result = await notification_service.create_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        channels=channels,
        notification_metadata=metadata
    )
    
    # Verify
    assert result is not None
    assert isinstance(result, NotificationResponse)
    assert result.user_id == user_id
    assert result.title == title
    assert result.message == message
    assert result.type == notification_type.value
    assert NotificationChannel.IN_APP.value in result.channels
    
    # Verify the notification was cached
    notification_service._cache_notification.assert_called_once()
    
    # Verify background tasks were created for sending notifications
    if notification_service.background_tasks:
        assert notification_service.background_tasks.add_task.called

@service_test
async def test_get_notifications(notification_service, mock_db_session, sample_notification):
    """Test getting user notifications."""
    # Setup
    user_id = uuid4()
    limit = 10
    offset = 0
    
    # Mock the session execute method
    mock_result = AsyncMock()
    mock_result.scalars().all.return_value = [sample_notification, sample_notification]
    mock_db_session.execute.return_value = mock_result
    
    # Execute
    results = await notification_service.get_notifications(
        user_id=user_id,
        limit=limit,
        offset=offset
    )
    
    # Verify
    assert len(results) == 2
    assert all(isinstance(result, NotificationResponse) for result in results)
    assert all(result.title == sample_notification.title for result in results)
    
    # Verify query parameters
    mock_db_session.execute.assert_called_once()

@service_test
async def test_get_unread_count(notification_service, mock_db_session):
    """Test getting unread notification count."""
    # Setup
    user_id = uuid4()
    expected_count = 5
    
    # Mock the session execute method
    mock_result = AsyncMock()
    mock_result.scalar_one.return_value = expected_count
    mock_db_session.execute.return_value = mock_result
    
    # Execute
    count = await notification_service.get_unread_count(user_id)
    
    # Verify
    assert count == expected_count
    mock_db_session.execute.assert_called_once()

@service_test
async def test_mark_as_read(notification_service, mock_db_session, sample_notification):
    """Test marking notifications as read."""
    # Setup
    user_id = uuid4()
    notification_ids = [uuid4(), uuid4()]
    
    # Mock the get_notifications_by_ids method
    notification_service.get_notifications_by_ids = AsyncMock(
        return_value=[NotificationResponse.model_validate(sample_notification)]
    )
    
    # Execute
    result = await notification_service.mark_as_read(
        notification_ids=notification_ids,
        user_id=user_id
    )
    
    # Verify
    assert len(result) == 1
    assert isinstance(result[0], NotificationResponse)
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_called_once()

@service_test
async def test_mark_as_read_not_found(notification_service, mock_db_session):
    """Test marking nonexistent notifications as read."""
    # Setup
    user_id = uuid4()
    notification_ids = [uuid4()]
    
    # Mock the get_notifications_by_ids method to return empty
    notification_service.get_notifications_by_ids = AsyncMock(return_value=[])
    
    # Execute and verify
    with pytest.raises(NotificationNotFoundError):
        await notification_service.mark_as_read(
            notification_ids=notification_ids,
            user_id=user_id
        )

@service_test
async def test_delete_notifications(notification_service, mock_db_session, sample_notification):
    """Test deleting notifications."""
    # Setup
    user_id = uuid4()
    notification_ids = [uuid4(), uuid4()]
    
    # Mock the get_notifications_by_ids method
    notification_service.get_notifications_by_ids = AsyncMock(
        return_value=[NotificationResponse.model_validate(sample_notification)]
    )
    
    # Execute
    await notification_service.delete_notifications(
        notification_ids=notification_ids,
        user_id=user_id
    )
    
    # Verify
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_called_once()

@service_test
async def test_delete_notifications_not_found(notification_service, mock_db_session):
    """Test deleting nonexistent notifications."""
    # Setup
    user_id = uuid4()
    notification_ids = [uuid4()]
    
    # Mock the get_notifications_by_ids method to return empty
    notification_service.get_notifications_by_ids = AsyncMock(return_value=[])
    
    # Execute and verify
    with pytest.raises(NotificationNotFoundError):
        await notification_service.delete_notifications(
            notification_ids=notification_ids,
            user_id=user_id
        )

@service_test
async def test_clear_all_notifications(notification_service, mock_db_session):
    """Test clearing all user notifications."""
    # Setup
    user_id = uuid4()
    
    # Execute
    await notification_service.clear_all_notifications(user_id)
    
    # Verify
    mock_db_session.execute.assert_called_once()
    mock_db_session.commit.assert_called_once()

@service_test
async def test_get_user_preferences(notification_service, mock_db_session, sample_user_preferences):
    """Test getting user notification preferences."""
    # Setup
    user_id = uuid4()
    
    # Mock the session execute method
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = sample_user_preferences
    mock_db_session.execute.return_value = mock_result
    
    # Execute
    result = await notification_service.get_user_preferences(user_id)
    
    # Verify
    assert result is not None
    assert NotificationChannel.IN_APP.value in result.enabled_channels
    assert NotificationChannel.EMAIL.value in result.enabled_channels

@service_test
async def test_update_preferences(notification_service, mock_db_session, sample_user_preferences):
    """Test updating user notification preferences."""
    # Setup
    user_id = uuid4()
    preferences_data = {
        "enabled_channels": [NotificationChannel.IN_APP.value, NotificationChannel.PUSH.value],
        "do_not_disturb": True,
        "minimum_priority": NotificationPriority.HIGH.value
    }
    
    # Mock the session execute method
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = sample_user_preferences
    mock_db_session.execute.return_value = mock_result
    
    # Execute
    result = await notification_service.update_preferences(
        user_id=user_id,
        preferences_data=preferences_data
    )
    
    # Verify
    assert result is not None
    assert NotificationChannel.IN_APP.value in result.enabled_channels
    assert NotificationChannel.PUSH.value in result.enabled_channels
    assert result.do_not_disturb is True
    assert result.minimum_priority == NotificationPriority.HIGH.value
    mock_db_session.commit.assert_called_once()

@service_test
@patch('core.services.notification.email_service.send_email')
async def test_send_password_reset_email(mock_send_email, notification_service):
    """Test sending password reset email."""
    # Setup
    email = "test@example.com"
    reset_token = "test_reset_token"
    
    # Mock background tasks
    mock_background_tasks = MagicMock()
    notification_service.set_background_tasks(mock_background_tasks)
    
    # Execute
    await notification_service.send_password_reset_email(
        email=email,
        reset_token=reset_token
    )
    
    # Verify
    mock_background_tasks.add_task.assert_called_once()

@service_test
@patch('core.services.notification.email_service.send_email')
async def test_send_magic_link_email(mock_send_email, notification_service):
    """Test sending magic link email."""
    # Setup
    email = "test@example.com"
    token = "test_magic_link_token"
    
    # Mock background tasks
    mock_background_tasks = MagicMock()
    notification_service.set_background_tasks(mock_background_tasks)
    
    # Execute
    await notification_service.send_magic_link_email(
        email=email,
        token=token
    )
    
    # Verify
    mock_background_tasks.add_task.assert_called_once()

@service_test
async def test_cache_notification(notification_service, mock_redis_client, sample_notification):
    """Test caching a notification."""
    # Initialize Redis client
    notification_service._redis_client = mock_redis_client
    notification_service._redis_enabled = True
    
    # Execute
    await notification_service._cache_notification(sample_notification)
    
    # Verify
    mock_redis_client.set.assert_called_once()

@service_test
async def test_set_background_tasks(notification_service):
    """Test setting background tasks."""
    # Setup
    mock_background_tasks = MagicMock()
    
    # Execute
    notification_service.set_background_tasks(mock_background_tasks)
    
    # Verify
    assert notification_service.background_tasks is mock_background_tasks

@service_test
async def test_convert_to_response(notification_service, sample_notification):
    """Test converting notification to response."""
    # Execute
    result = notification_service._convert_to_response(sample_notification)
    
    # Verify
    assert isinstance(result, NotificationResponse)
    assert result.id == sample_notification.id
    assert result.user_id == sample_notification.user_id
    assert result.title == sample_notification.title
    assert result.message == sample_notification.message
    assert result.type == sample_notification.type
    assert result.channels == sample_notification.channels
    assert result.priority == sample_notification.priority
    assert result.status == sample_notification.status

@service_test
async def test_convert_notification_frequency(notification_service):
    """Test converting notification frequency dictionary."""
    # Setup
    freq_dict = {
        NotificationType.SYSTEM.value: {"type": NotificationType.SYSTEM.value, "frequency": NotificationFrequency.IMMEDIATE.value},
        NotificationType.DEAL.value: {"type": NotificationType.DEAL.value, "frequency": NotificationFrequency.DAILY.value}
    }
    
    # Execute
    result = notification_service._convert_notification_frequency(freq_dict)
    
    # Verify
    assert NotificationType.SYSTEM in result
    assert result[NotificationType.SYSTEM] == NotificationFrequency.IMMEDIATE
    assert NotificationType.DEAL in result
    assert result[NotificationType.DEAL] == NotificationFrequency.DAILY

@service_test
async def test_convert_time_windows(notification_service):
    """Test converting time windows dictionary."""
    # Setup
    windows_dict = {
        NotificationChannel.IN_APP.value: {"start_time": "08:00", "end_time": "20:00", "timezone": "UTC"},
        NotificationChannel.EMAIL.value: {"start_time": "09:00", "end_time": "18:00", "timezone": "UTC"}
    }
    
    # Execute
    result = notification_service._convert_time_windows(windows_dict)
    
    # Verify
    assert NotificationChannel.IN_APP in result
    assert result[NotificationChannel.IN_APP].start_time.hour == 8
    assert result[NotificationChannel.IN_APP].end_time.hour == 20
    assert NotificationChannel.EMAIL in result
    assert result[NotificationChannel.EMAIL].start_time.hour == 9
    assert result[NotificationChannel.EMAIL].end_time.hour == 18 