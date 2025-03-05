"""Tests for the notification model."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from core.models.notification import Notification, NotificationType, NotificationStatus, NotificationPriority, NotificationChannel
from core.models.user import User
from core.models.deal import Deal
from core.models.enums import DealStatus, MarketType, MarketCategory
from core.models.market import Market

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_creation(db_session):
    """Test creating a notification in the database."""
    # Create a user
    user = User(
        email="notification_test@example.com",
        name="Notification Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a market
    market = Market(
        name="Notification Test Market",
        description="A market for testing notification model",
        type=MarketType.TEST.value.lower(),
        user_id=user.id
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Notification Test Deal",
        description="A deal for testing notification model",
        url="https://example.com/test-deal",
        price=19.99,
        currency="USD",
        status=DealStatus.PENDING.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user.id,
        market_id=market.id
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Test Notification",
        message="This is a test notification",
        type=NotificationType.DEAL.value.lower(),
        status=NotificationStatus.PENDING.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        notification_metadata={
            "importance": "high",
            "category": "deal"
        },
        channels=[NotificationChannel.IN_APP.value]
    )
    
    # Add to session and commit
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)
    
    # Verify the notification was created with an ID
    assert notification.id is not None
    assert isinstance(notification.id, uuid.UUID)
    assert notification.title == "Test Notification"
    assert notification.message == "This is a test notification"
    assert notification.type == NotificationType.DEAL.value.lower()
    assert notification.status == NotificationStatus.PENDING.value.lower()
    assert notification.user_id == user.id
    assert notification.deal_id == deal.id
    
    # Verify metadata
    assert notification.notification_metadata["importance"] == "high"
    assert notification.notification_metadata["category"] == "deal"
    
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
        name="Notification Relationship Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a market
    market = Market(
        name="Notification Relationship Test Market",
        description="A market for testing notification relationships",
        type=MarketType.TEST.value.lower(),
        user_id=user.id
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Notification Relationship Test Deal",
        description="A deal for testing notification relationships",
        status=DealStatus.PENDING.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user.id,
        market_id=market.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Relationship Test Notification",
        message="This is a test notification for relationships",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.PENDING.value.lower(),
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
    """Test updating a notification in the database."""
    # Create a user
    user = User(
        email="notification_update@example.com",
        name="Notification Update Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Original Notification Title",
        message="This is the original notification content",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.PENDING.value.lower(),
        user_id=user.id,
        notification_metadata={"importance": "medium"}
    )
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)
    
    # Update the notification
    notification.title = "Updated Notification Title"
    notification.message = "This is an updated notification content"
    notification.status = NotificationStatus.READ.value.lower()
    
    # Update the notification_metadata
    notification.notification_metadata = {
        "importance": "high",
        "read_at": datetime.utcnow().isoformat()
    }
    
    await db_session.commit()
    await db_session.refresh(notification)
    
    # Verify the updates
    assert notification.title == "Updated Notification Title"
    assert notification.message == "This is an updated notification content"
    assert notification.status == NotificationStatus.READ.value.lower()
    assert notification.notification_metadata["importance"] == "high"
    assert "read_at" in notification.notification_metadata
    
    # Verify updated_at was updated
    assert notification.updated_at is not None
    assert isinstance(notification.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_deletion(db_session):
    """Test deleting a notification."""
    # Create a user
    user = User(
        email="notification_delete@example.com",
        name="Notification Delete Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a notification
    notification = Notification(
        title="Delete Test Notification",
        message="This is a test notification for deletion",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.PENDING.value.lower(),
        user_id=user.id,
        notification_metadata={"test": True}
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
        name="Notification Query Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create unread notifications
    unread_notification1 = Notification(
        title="Unread Notification 1",
        message="This is an unread notification",
        type=NotificationType.DEAL.value.lower(),
        status=NotificationStatus.PENDING.value.lower(),
        user_id=user.id,
        notification_metadata={"test": True}
    )
    
    unread_notification2 = Notification(
        title="Unread Notification 2",
        message="This is another unread notification",
        type=NotificationType.SYSTEM.value.lower(),
        status=NotificationStatus.PENDING.value.lower(),
        user_id=user.id,
        notification_metadata={"test": True}
    )
    
    # Create read notification
    read_notification = Notification(
        title="Read Notification",
        message="This is a read notification",
        type=NotificationType.DEAL.value.lower(),
        status=NotificationStatus.READ.value.lower(),
        user_id=user.id,
        notification_metadata={"test": True}
    )
    
    db_session.add_all([unread_notification1, unread_notification2, read_notification])
    await db_session.commit()
    
    # Query unread notifications
    stmt = select(Notification).where(
        Notification.user_id == user.id,
        Notification.status == NotificationStatus.PENDING.value.lower()
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