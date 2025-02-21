"""Test goal processing tasks."""

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
from core.models.token import TokenTransaction
from core.tasks.goal_tasks import process_goals, update_goal_analytics, cleanup_completed_goals
from core.exceptions import GoalError, ValidationError

@pytest.mark.asyncio
class TestGoalTasks:
    """Test cases for goal processing tasks."""
    
    @pytest.fixture(autouse=True)
    async def setup(self, async_session: AsyncSession):
        """Setup test data."""
        self.session = async_session
        
        # Create test user
        self.user = await User.create(
            self.session,
            email="test@example.com",
            password="hashed_password",
            status=UserStatus.ACTIVE.value,
            token_balance=Decimal("100.0")
        )
        
        # Create test market
        self.market = Market(
            name="Test Market",
            type=MarketType.AMAZON,
            status=MarketStatus.ACTIVE,
            api_endpoint="https://api.test.com",
            api_key="test_key"
        )
        self.session.add(self.market)
        
        # Create test goals
        self.active_goal = Goal(
            user_id=self.user.id,
            title="Active Goal",
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
        
        self.completed_goal = Goal(
            user_id=self.user.id,
            title="Completed Goal",
            item_category="electronics",
            constraints={
                "max_price": 1000,
                "min_price": 500
            },
            status="completed",
            deadline=datetime.utcnow() - timedelta(days=1)
        )
        
        self.session.add_all([self.active_goal, self.completed_goal])
        await self.session.commit()
        await self.session.refresh(self.user)
        await self.session.refresh(self.market)
        await self.session.refresh(self.active_goal)
        await self.session.refresh(self.completed_goal)

    async def test_process_goals(self):
        """Test goal processing."""
        # Create test deal
        deal = Deal(
            user_id=self.user.id,
            goal_id=self.active_goal.id,
            market_id=self.market.id,
            title="Test Deal",
            url="https://test.com/deal",
            price=Decimal("750.0"),
            original_price=Decimal("1000.0"),
            currency="USD",
            source="amazon",
            status="active"
        )
        self.session.add(deal)
        await self.session.commit()
        
        # Process goals
        await process_goals(user_id=self.user.id, goals=[self.active_goal])
        
        # Verify goal was processed
        processed_goal = await self.session.execute(
            select(Goal).where(Goal.id == self.active_goal.id)
        )
        processed_goal = processed_goal.scalar_one()
        
        assert processed_goal.last_checked_at is not None
        assert processed_goal.total_deals_found >= 1
        assert processed_goal.success_rate >= 0.0

    async def test_update_goal_analytics(self):
        """Test goal analytics update."""
        # Create test deals
        deals = [
            Deal(
                user_id=self.user.id,
                goal_id=self.active_goal.id,
                market_id=self.market.id,
                title=f"Deal {i}",
                url=f"https://test.com/deal/{i}",
                price=Decimal("750.0"),
                original_price=Decimal("1000.0"),
                currency="USD",
                source="amazon",
                status="active"
            )
            for i in range(3)
        ]
        self.session.add_all(deals)
        await self.session.commit()
        
        # Update analytics
        await update_goal_analytics(goal_id=self.active_goal.id, user_id=self.user.id)
        
        # Verify analytics were updated
        updated_goal = await self.session.execute(
            select(Goal).where(Goal.id == self.active_goal.id)
        )
        updated_goal = updated_goal.scalar_one()
        
        assert updated_goal.total_deals_found == 3
        assert updated_goal.success_rate > 0.0
        assert updated_goal.last_analytics_update is not None

    async def test_cleanup_completed_goals(self):
        """Test cleanup of completed goals."""
        # Add some expired completed goals
        expired_goals = [
            Goal(
                user_id=self.user.id,
                title=f"Expired Goal {i}",
                item_category="electronics",
                constraints={"max_price": 1000},
                status="completed",
                deadline=datetime.utcnow() - timedelta(days=31)  # Expired
            )
            for i in range(3)
        ]
        self.session.add_all(expired_goals)
        await self.session.commit()
        
        # Run cleanup
        await cleanup_completed_goals()
        
        # Verify cleanup
        remaining_goals = await self.session.execute(
            select(Goal).where(Goal.status == "completed")
        )
        remaining_goals = remaining_goals.scalars().all()
        
        # Should only have our original completed goal (not expired)
        assert len(remaining_goals) == 1
        assert remaining_goals[0].id == self.completed_goal.id

    async def test_goal_validation(self):
        """Test goal validation during processing."""
        # Try to create invalid goal
        invalid_goal = Goal(
            user_id=self.user.id,
            title="Invalid Goal",
            item_category="invalid_category",  # Invalid category
            constraints={},  # Empty constraints
            status="active"
        )
        self.session.add(invalid_goal)
        await self.session.commit()
        
        # Process should handle invalid goal gracefully
        await process_goals(user_id=self.user.id, goals=[invalid_goal])
        
        # Verify goal was marked as failed
        failed_goal = await self.session.execute(
            select(Goal).where(Goal.id == invalid_goal.id)
        )
        failed_goal = failed_goal.scalar_one()
        assert failed_goal.status == "failed"
        assert "invalid category" in failed_goal.failure_reason.lower()

    async def test_goal_token_deduction(self):
        """Test token deduction during goal processing."""
        initial_balance = self.user.token_balance
        
        # Process goals
        await process_goals(user_id=self.user.id, goals=[self.active_goal])
        
        # Verify token deduction
        updated_user = await self.session.execute(
            select(User).where(User.id == self.user.id)
        )
        updated_user = updated_user.scalar_one()
        assert updated_user.token_balance < initial_balance
        
        # Verify token transaction was created
        transactions = await self.session.execute(
            select(TokenTransaction).where(TokenTransaction.user_id == self.user.id)
        )
        transactions = transactions.scalars().all()
        assert len(transactions) > 0
        assert any(t.type == "deduction" for t in transactions) 