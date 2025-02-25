"""Test deal processing tasks."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import User, UserStatus
from core.models.goal import Goal
from core.models.deal import Deal
from core.models.market import Market, MarketType, MarketStatus
from core.models.notification import Notification
from core.tasks.price_monitor import monitor_price_changes, update_price_history, analyze_price_trends
from core.exceptions import DealError, ValidationError

@pytest.mark.asyncio
class TestDealTasks:
    """Test cases for deal processing tasks."""
    
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
            status="active"
        )
        self.session.add(self.goal)
        
        # Create test deals
        self.active_deal = Deal(
            user_id=self.user.id,
            goal_id=self.goal.id,
            market_id=self.market.id,
            title="Active Deal",
            url="https://test.com/deal1",
            price=Decimal("750.0"),
            original_price=Decimal("1000.0"),
            currency="USD",
            source="amazon",
            status="active",
            found_at=datetime.utcnow()
        )
        
        self.expired_deal = Deal(
            user_id=self.user.id,
            goal_id=self.goal.id,
            market_id=self.market.id,
            title="Expired Deal",
            url="https://test.com/deal2",
            price=Decimal("600.0"),
            original_price=Decimal("800.0"),
            currency="USD",
            source="amazon",
            status="active",
            found_at=datetime.utcnow() - timedelta(days=31),  # Expired
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        
        self.session.add_all([self.active_deal, self.expired_deal])
        await self.session.commit()
        
        # Refresh objects
        await self.session.refresh(self.user)
        await self.session.refresh(self.market)
        await self.session.refresh(self.goal)
        await self.session.refresh(self.active_deal)
        await self.session.refresh(self.expired_deal)

    async def test_process_deals(self):
        """Test deal processing."""
        # Process deals
        deal_ids = [str(self.active_deal.id), str(self.expired_deal.id)]
        changes = await monitor_price_changes(self.session, deal_ids)
        
        # Verify deals were processed
        processed_deals = await self.session.execute(
            select(Deal).where(Deal.user_id == self.user.id)
        )
        processed_deals = processed_deals.scalars().all()
        
        # Check active deal
        active = next(d for d in processed_deals if d.id == self.active_deal.id)
        assert active.status == "active"
        assert active.last_checked is not None
        
        # Check expired deal
        expired = next(d for d in processed_deals if d.id == self.expired_deal.id)
        assert expired.status == "active"  # Status is managed by a different process now
        assert expired.last_checked is not None

    async def test_update_deal_prices(self):
        """Test deal price updates."""
        # Update prices
        new_price = Decimal("700.0")
        price_point = await update_price_history(
            session=self.session,
            deal_id=str(self.active_deal.id),
            new_price=new_price,
            source="test"
        )
        
        # Verify price was updated
        updated_deal = await self.session.execute(
            select(Deal).where(Deal.id == self.active_deal.id)
        )
        updated_deal = updated_deal.scalar_one()
        
        assert price_point is not None
        assert price_point.price == new_price
        assert price_point.deal_id == self.active_deal.id

    async def test_price_trends(self):
        """Test price trend analysis."""
        # First add some price history
        prices = [
            Decimal("800.0"),
            Decimal("750.0"),
            Decimal("700.0")
        ]
        
        for price in prices:
            await update_price_history(
                session=self.session,
                deal_id=str(self.active_deal.id),
                new_price=price,
                source="test"
            )
        
        # Analyze trends
        trends = await analyze_price_trends(
            session=self.session,
            deal_id=str(self.active_deal.id)
        )
        
        assert trends is not None
        assert "price_trend" in trends
        assert trends["price_trend"] == "decreasing"
        assert trends["total_drop"] > 0
        assert trends["drop_percentage"] > 0

    async def test_cleanup_expired_deals(self):
        """Test cleanup of expired deals."""
        # Add some expired deals
        expired_deals = [
            Deal(
                user_id=self.user.id,
                goal_id=self.goal.id,
                market_id=self.market.id,
                title=f"Old Deal {i}",
                url=f"https://test.com/old-deal-{i}",
                price=Decimal("600.0"),
                original_price=Decimal("800.0"),
                currency="USD",
                source="amazon",
                status="active",
                found_at=datetime.utcnow() - timedelta(days=31),
                expires_at=datetime.utcnow() - timedelta(days=1)
            )
            for i in range(3)
        ]
        self.session.add_all(expired_deals)
        await self.session.commit()
        
        # Run cleanup
        await cleanup_expired_deals()
        
        # Verify cleanup
        remaining_deals = await self.session.execute(
            select(Deal).where(Deal.status == "active")
        )
        remaining_deals = remaining_deals.scalars().all()
        
        # Should only have our original active deal
        assert len(remaining_deals) == 1
        assert remaining_deals[0].id == self.active_deal.id

    async def test_deal_validation(self):
        """Test deal validation during processing."""
        # Create invalid deal
        invalid_deal = Deal(
            user_id=self.user.id,
            goal_id=self.goal.id,
            market_id=self.market.id,
            title="Invalid Deal",
            url="invalid-url",  # Invalid URL
            price=Decimal("-100.0"),  # Invalid price
            currency="INVALID",  # Invalid currency
            source="unknown",
            status="active"
        )
        self.session.add(invalid_deal)
        await self.session.commit()
        
        # Process should handle invalid deal gracefully
        await process_deals(user_id=self.user.id, deals=[invalid_deal])
        
        # Verify deal was marked as invalid
        failed_deal = await self.session.execute(
            select(Deal).where(Deal.id == invalid_deal.id)
        )
        failed_deal = failed_deal.scalar_one()
        assert failed_deal.status == "invalid"
        assert failed_deal.failure_reason is not None

    async def test_deal_notifications(self):
        """Test notifications during deal processing."""
        # Process deals which should trigger notifications
        await process_deals(user_id=self.user.id, deals=[self.active_deal])
        
        # Verify notifications were created
        notifications = await self.session.execute(
            select(Notification).where(
                Notification.user_id == self.user.id,
                Notification.deal_id == self.active_deal.id
            )
        )
        notifications = notifications.scalars().all()
        
        assert len(notifications) > 0
        assert any("price" in n.message.lower() for n in notifications) 