"""Test notification processing tasks."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock

from core.models.user import User, UserStatus
from core.models.goal import Goal
from core.models.deal import Deal
from core.models.market import Market, MarketType, MarketStatus
from core.models.notification import Notification, NotificationPriority, NotificationStatus
from core.services.notification import NotificationService

@pytest.mark.asyncio
class TestNotificationTasks:
    """Test cases for notification processing tasks."""
    
    @pytest.fixture(autouse=True)
    async def setup(self, async_session: AsyncSession):
        """Setup test data."""
        self.session = async_session
        
        # Create test user
        self.user = User(
            email="test@example.com",
            password="hashed_password",
            status=UserStatus.ACTIVE.value,
            token_balance=Decimal("100.0")
        )
        self.session.add(self.user)
        
        # Create test market
        self.market = Market(
            name="Test Market",
            type=MarketType.AMAZON,
            status=MarketStatus.ACTIVE,
            api_endpoint="https://api.test.com",
            api_key="test_key"
        )
        self.session.add(self.market)
        
        # Create test goal
        self.goal = Goal(
            user_id=self.user.id,
            title="Test Goal",
            item_category="electronics",
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"]
            },
            status="active",
            deadline=datetime.utcnow() + timedelta(days=7)
        )
        self.session.add(self.goal)
        
        # Create test deal
        self.deal = Deal(
            user_id=self.user.id,
            goal_id=self.goal.id,
            market_id=self.market.id,
            title="Test Deal",
            url="https://test.com/deal",
            price=Decimal("750.0"),
            original_price=Decimal("1000.0"),
            currency="USD",
            source="amazon",
            status="active"
        )
        self.session.add(self.deal)
        
        # Create test notifications
        self.pending_notification = Notification(
            user_id=self.user.id,
            goal_id=self.goal.id,
            deal_id=self.deal.id,
            title="Pending Notification",
            message="Test notification message",
            type="deal_match",
            priority=NotificationPriority.HIGH,
            status=NotificationStatus.PENDING,
            channels=["email", "in_app"]
        )
        
        self.old_notification = Notification(
            user_id=self.user.id,
            goal_id=self.goal.id,
            deal_id=self.deal.id,
            title="Old Notification",
            message="Old test notification",
            type="price_drop",
            priority=NotificationPriority.MEDIUM,
            status=NotificationStatus.DELIVERED,
            channels=["in_app"],
            created_at=datetime.utcnow() - timedelta(days=31)  # Old notification
        )
        
        self.session.add_all([self.pending_notification, self.old_notification])
        await self.session.commit()
        
        # Refresh objects
        await self.session.refresh(self.user)
        await self.session.refresh(self.market)
        await self.session.refresh(self.goal)
        await self.session.refresh(self.deal)
        await self.session.refresh(self.pending_notification)
        await self.session.refresh(self.old_notification)

    async def test_process_notifications(self):
        """Test notification processing."""
        notification_service = NotificationService(self.session)
        await notification_service.process_notifications()
        
        # Verify notifications were processed
        processed_notification = await self.session.execute(
            select(Notification).where(Notification.id == self.pending_notification.id)
        )
        processed_notification = processed_notification.scalar_one()
        
        assert processed_notification.status == NotificationStatus.SENT
        assert processed_notification.sent_at is not None

    async def test_cleanup_old_notifications(self):
        """Test cleanup of old notifications."""
        notification_service = NotificationService(self.session)
        await notification_service.cleanup_old_notifications(days=30)
        
        # Verify cleanup
        remaining_notifications = await self.session.execute(
            select(Notification)
        )
        remaining_notifications = remaining_notifications.scalars().all()
        
        # Should only have our pending notification
        assert len(remaining_notifications) == 1
        assert remaining_notifications[0].id == self.pending_notification.id

    async def test_notification_validation(self):
        """Test notification validation during processing."""
        # Try to create invalid notification
        invalid_notification = Notification(
            user_id=self.user.id,
            title="Invalid Notification",
            message="",  # Empty message
            type="invalid_type",  # Invalid type
            priority="invalid",  # Invalid priority
            status=NotificationStatus.PENDING,
            channels=[]  # Empty channels
        )
        self.session.add(invalid_notification)
        await self.session.commit()
        
        # Process should handle invalid notification gracefully
        notification_service = NotificationService(self.session)
        await notification_service.process_notifications()
        
        # Verify notification was marked as failed
        failed_notification = await self.session.execute(
            select(Notification).where(Notification.id == invalid_notification.id)
        )
        failed_notification = failed_notification.scalar_one()
        assert failed_notification.status == NotificationStatus.FAILED

    async def test_notification_channels(self):
        """Test notification processing for different channels."""
        # Create notifications for different channels
        channel_notifications = [
            Notification(
                user_id=self.user.id,
                goal_id=self.goal.id,
                deal_id=self.deal.id,
                title=f"Channel Test {channel}",
                message=f"Test notification for {channel}",
                type="test",
                priority=NotificationPriority.MEDIUM,
                status=NotificationStatus.PENDING,
                channels=[channel]
            )
            for channel in ["email", "in_app", "push"]
        ]
        self.session.add_all(channel_notifications)
        await self.session.commit()
        
        # Process notifications
        notification_service = NotificationService(self.session)
        await notification_service.process_notifications()
        
        # Verify each channel was processed
        processed_notifications = await self.session.execute(
            select(Notification).where(
                Notification.id.in_([n.id for n in channel_notifications])
            )
        )
        processed_notifications = processed_notifications.scalars().all()
        
        for notification in processed_notifications:
            assert notification.status == NotificationStatus.SENT
            assert notification.sent_at is not None

    async def test_notification_priority(self):
        """Test notification processing respects priority."""
        # Create notifications with different priorities
        priority_notifications = [
            Notification(
                user_id=self.user.id,
                goal_id=self.goal.id,
                deal_id=self.deal.id,
                title=f"Priority Test {priority.name}",
                message=f"Test notification with {priority.name} priority",
                type="test",
                priority=priority,
                status=NotificationStatus.PENDING,
                channels=["in_app"]
            )
            for priority in [NotificationPriority.LOW, NotificationPriority.MEDIUM, NotificationPriority.HIGH]
        ]
        self.session.add_all(priority_notifications)
        await self.session.commit()
        
        # Process notifications
        notification_service = NotificationService(self.session)
        await notification_service.process_notifications()
        
        # Verify notifications were processed in priority order
        processed_notifications = await self.session.execute(
            select(Notification).where(
                Notification.id.in_([n.id for n in priority_notifications])
            ).order_by(Notification.sent_at)
        )
        processed_notifications = processed_notifications.scalars().all()
        
        # High priority should be processed first
        assert processed_notifications[0].priority == NotificationPriority.HIGH
        assert processed_notifications[-1].priority == NotificationPriority.LOW 