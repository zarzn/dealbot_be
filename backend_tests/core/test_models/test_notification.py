"""Tests for the notification model."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from core.models.notification import Notification, NotificationType, NotificationStatus
from core.models.user import User
from core.models.deal import Deal
from core.models.enums import DealStatus, MarketType

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_creation(db_session):
    """Test creating a notification in the database."""
    # Create a user
    user = User(
        email="notification_test@example.com",
        username="notificationuser",
        full_name="Notification Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Notification Test Deal",
        description="A deal for testing notification model",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Test Notification",
        content="This is a test notification",
        type=NotificationType.DEAL_UPDATE.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        metadata={
            "importance": "high",
            "category": "deal"
        }
    )
    
    # Add to session and commit
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)
    
    # Verify the notification was created with an ID
    assert notification.id is not None
    assert isinstance(notification.id, uuid.UUID)
    assert notification.title == "Test Notification"
    assert notification.content == "This is a test notification"
    assert notification.type == NotificationType.DEAL_UPDATE.value.lower()
    assert notification.status == NotificationStatus.UNREAD.value.lower()
    assert notification.user_id == user.id
    assert notification.deal_id == deal.id
    
    # Verify metadata
    assert notification.metadata["importance"] == "high"
    assert notification.metadata["category"] == "deal"
    
    # Verify created_at and updated_at were set
    assert notification.created_at is not None
    assert notification.updated_at is not None
    assert isinstance(notification.created_at, datetime)
    assert isinstance(notification.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_relationships(db_session):
    """Test notification relationships with user and deal."""
    # Create a user
    user = User(
        email="notification_rel_test@example.com",
        username="notificationreluser",
        full_name="Notification Relationship Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Notification Relationship Test Deal",
        description="A deal for testing notification relationships",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Relationship Test Notification",
        content="This is a test notification for relationships",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        metadata={"test": True}
    )
    db_session.add(notification)
    await db_session.commit()
    
    # Query the notification with relationships
    stmt = select(Notification).where(Notification.id == notification.id)
    result = await db_session.execute(stmt)
    loaded_notification = result.scalar_one()
    
    # Verify relationships
    assert loaded_notification.id == notification.id
    assert loaded_notification.user_id == user.id
    assert loaded_notification.deal_id == deal.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_update(db_session):
    """Test updating a notification."""
    # Create a user
    user = User(
        email="notification_update@example.com",
        username="notificationupdateuser",
        full_name="Notification Update Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Update Test Notification",
        content="This is a test notification for updates",
        type=NotificationType.DEAL_UPDATE.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        metadata={"importance": "medium"}
    )
    db_session.add(notification)
    await db_session.commit()
    
    # Update the notification
    notification.title = "Updated Notification Title"
    notification.content = "This is an updated notification content"
    notification.status = NotificationStatus.READ.value.lower()
    notification.metadata["importance"] = "high"
    notification.metadata["read_at"] = datetime.utcnow().isoformat()
    
    await db_session.commit()
    await db_session.refresh(notification)
    
    # Verify the updates
    assert notification.title == "Updated Notification Title"
    assert notification.content == "This is an updated notification content"
    assert notification.status == NotificationStatus.READ.value.lower()
    assert notification.metadata["importance"] == "high"
    assert "read_at" in notification.metadata
    
    # Verify updated_at was updated
    assert notification.updated_at is not None

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_deletion(db_session):
    """Test deleting a notification."""
    # Create a user
    user = User(
        email="notification_delete@example.com",
        username="notificationdeleteuser",
        full_name="Notification Delete Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Delete Test Notification",
        content="This is a test notification for deletion",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(notification)
    await db_session.commit()
    
    # Get the notification ID
    notification_id = notification.id
    
    # Delete the notification
    await db_session.delete(notification)
    await db_session.commit()
    
    # Try to find the deleted notification
    stmt = select(Notification).where(Notification.id == notification_id)
    result = await db_session.execute(stmt)
    deleted_notification = result.scalar_one_or_none()
    
    # Verify the notification was deleted
    assert deleted_notification is None

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_query_by_status(db_session):
    """Test querying notifications by status."""
    # Create a user
    user = User(
        email="notification_query@example.com",
        username="notificationqueryuser",
        full_name="Notification Query Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create unread notifications
    unread_notification1 = Notification(
        title="Unread Notification 1",
        content="This is an unread notification",
        type=NotificationType.DEAL_UPDATE.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    
    unread_notification2 = Notification(
        title="Unread Notification 2",
        content="This is another unread notification",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    
    # Create read notification
    read_notification = Notification(
        title="Read Notification",
        content="This is a read notification",
        type=NotificationType.DEAL_UPDATE.value.lower(),
        status=NotificationStatus.READ.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    
    db_session.add_all([unread_notification1, unread_notification2, read_notification])
    await db_session.commit()
    
    # Query unread notifications
    stmt = select(Notification).where(
        Notification.user_id == user.id,
        Notification.status == NotificationStatus.UNREAD.value.lower()
    )
    result = await db_session.execute(stmt)
    unread_notifications = result.scalars().all()
    
    # Verify unread notifications
    assert len(unread_notifications) == 2
    
    # Query read notifications
    stmt = select(Notification).where(
        Notification.user_id == user.id,
        Notification.status == NotificationStatus.READ.value.lower()
    )
    result = await db_session.execute(stmt)
    read_notifications = result.scalars().all()
    
    # Verify read notifications
    assert len(read_notifications) == 1 

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from core.models.notification import Notification, NotificationType, NotificationStatus
from core.models.user import User
from core.models.deal import Deal
from core.models.enums import DealStatus, MarketType

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_creation(db_session):
    """Test creating a notification in the database."""
    # Create a user
    user = User(
        email="notification_test@example.com",
        username="notificationuser",
        full_name="Notification Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Notification Test Deal",
        description="A deal for testing notification model",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Test Notification",
        content="This is a test notification",
        type=NotificationType.DEAL_UPDATE.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        metadata={
            "importance": "high",
            "category": "deal"
        }
    )
    
    # Add to session and commit
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)
    
    # Verify the notification was created with an ID
    assert notification.id is not None
    assert isinstance(notification.id, uuid.UUID)
    assert notification.title == "Test Notification"
    assert notification.content == "This is a test notification"
    assert notification.type == NotificationType.DEAL_UPDATE.value.lower()
    assert notification.status == NotificationStatus.UNREAD.value.lower()
    assert notification.user_id == user.id
    assert notification.deal_id == deal.id
    
    # Verify metadata
    assert notification.metadata["importance"] == "high"
    assert notification.metadata["category"] == "deal"
    
    # Verify created_at and updated_at were set
    assert notification.created_at is not None
    assert notification.updated_at is not None
    assert isinstance(notification.created_at, datetime)
    assert isinstance(notification.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_relationships(db_session):
    """Test notification relationships with user and deal."""
    # Create a user
    user = User(
        email="notification_rel_test@example.com",
        username="notificationreluser",
        full_name="Notification Relationship Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Notification Relationship Test Deal",
        description="A deal for testing notification relationships",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Relationship Test Notification",
        content="This is a test notification for relationships",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        metadata={"test": True}
    )
    db_session.add(notification)
    await db_session.commit()
    
    # Query the notification with relationships
    stmt = select(Notification).where(Notification.id == notification.id)
    result = await db_session.execute(stmt)
    loaded_notification = result.scalar_one()
    
    # Verify relationships
    assert loaded_notification.id == notification.id
    assert loaded_notification.user_id == user.id
    assert loaded_notification.deal_id == deal.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_update(db_session):
    """Test updating a notification."""
    # Create a user
    user = User(
        email="notification_update@example.com",
        username="notificationupdateuser",
        full_name="Notification Update Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Update Test Notification",
        content="This is a test notification for updates",
        type=NotificationType.DEAL_UPDATE.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        metadata={"importance": "medium"}
    )
    db_session.add(notification)
    await db_session.commit()
    
    # Update the notification
    notification.title = "Updated Notification Title"
    notification.content = "This is an updated notification content"
    notification.status = NotificationStatus.READ.value.lower()
    notification.metadata["importance"] = "high"
    notification.metadata["read_at"] = datetime.utcnow().isoformat()
    
    await db_session.commit()
    await db_session.refresh(notification)
    
    # Verify the updates
    assert notification.title == "Updated Notification Title"
    assert notification.content == "This is an updated notification content"
    assert notification.status == NotificationStatus.READ.value.lower()
    assert notification.metadata["importance"] == "high"
    assert "read_at" in notification.metadata
    
    # Verify updated_at was updated
    assert notification.updated_at is not None

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_deletion(db_session):
    """Test deleting a notification."""
    # Create a user
    user = User(
        email="notification_delete@example.com",
        username="notificationdeleteuser",
        full_name="Notification Delete Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Delete Test Notification",
        content="This is a test notification for deletion",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(notification)
    await db_session.commit()
    
    # Get the notification ID
    notification_id = notification.id
    
    # Delete the notification
    await db_session.delete(notification)
    await db_session.commit()
    
    # Try to find the deleted notification
    stmt = select(Notification).where(Notification.id == notification_id)
    result = await db_session.execute(stmt)
    deleted_notification = result.scalar_one_or_none()
    
    # Verify the notification was deleted
    assert deleted_notification is None

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_query_by_status(db_session):
    """Test querying notifications by status."""
    # Create a user
    user = User(
        email="notification_query@example.com",
        username="notificationqueryuser",
        full_name="Notification Query Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create unread notifications
    unread_notification1 = Notification(
        title="Unread Notification 1",
        content="This is an unread notification",
        type=NotificationType.DEAL_UPDATE.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    
    unread_notification2 = Notification(
        title="Unread Notification 2",
        content="This is another unread notification",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.UNREAD.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    
    # Create read notification
    read_notification = Notification(
        title="Read Notification",
        content="This is a read notification",
        type=NotificationType.DEAL_UPDATE.value.lower(),
        status=NotificationStatus.READ.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    
    db_session.add_all([unread_notification1, unread_notification2, read_notification])
    await db_session.commit()
    
    # Query unread notifications
    stmt = select(Notification).where(
        Notification.user_id == user.id,
        Notification.status == NotificationStatus.UNREAD.value.lower()
    )
    result = await db_session.execute(stmt)
    unread_notifications = result.scalars().all()
    
    # Verify unread notifications
    assert len(unread_notifications) == 2
    
    # Query read notifications
    stmt = select(Notification).where(
        Notification.user_id == user.id,
        Notification.status == NotificationStatus.READ.value.lower()
    )
    result = await db_session.execute(stmt)
    read_notifications = result.scalars().all()
    
    # Verify read notifications
    assert len(read_notifications) == 1 