"""Goal model tests."""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from core.models.goal import Goal, GoalStatus, GoalPriority
from core.models.market import MarketCategory
from core.exceptions import (
    GoalValidationError,
    GoalConstraintError,
    InvalidGoalConstraintsError
)
import asyncio
from unittest.mock import patch
import time_machine

@pytest.mark.asyncio
async def test_create_goal(async_session: AsyncSession, test_user):
    """Test creating a goal."""
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"],
            "keywords": ["laptop", "gaming"]
        },
        priority=GoalPriority.MEDIUM,
        status=GoalStatus.ACTIVE
    )
    
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.id is not None
    assert goal.title == "Test Goal"
    assert goal.item_category == MarketCategory.ELECTRONICS.value
    assert goal.constraints["max_price"] == 1000
    assert goal.constraints["min_price"] == 500
    assert "laptop" in goal.constraints["keywords"]
    assert goal.priority == GoalPriority.MEDIUM.value
    assert goal.status == GoalStatus.ACTIVE.value
    assert goal.created_at is not None
    assert goal.updated_at is not None

@pytest.mark.asyncio
async def test_invalid_item_category(async_session: AsyncSession, test_user):
    """Test invalid item category validation."""
    with pytest.raises(GoalValidationError, match="Invalid item category"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category="invalid_category",  # Invalid category
            priority=GoalPriority.MEDIUM,
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"],
                "keywords": ["test"]
            }
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_invalid_constraints_format(async_session: AsyncSession, test_user):
    """Test invalid constraints format validation."""
    with pytest.raises(GoalConstraintError, match="Invalid constraints format"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            priority=GoalPriority.MEDIUM,
            constraints="not-a-json-object"  # Invalid format
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_invalid_price_constraints(async_session: AsyncSession, test_user):
    """Test invalid price constraints validation."""
    with pytest.raises(GoalConstraintError, match="Min price must be less than max price"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            priority=GoalPriority.MEDIUM,
            constraints={
                "max_price": 500,  # Lower than min_price
                "min_price": 1000,
                "brands": ["Test"],
                "conditions": ["new"],
                "keywords": ["test"]
            }
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_max_matches_validation(async_session: AsyncSession, test_user):
    """Test max matches validation."""
    with pytest.raises(GoalValidationError, match="Max matches must be positive"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            priority=GoalPriority.MEDIUM,
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"],
                "keywords": ["test"]
            },
            max_matches=-1  # Invalid value
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_max_tokens_validation(async_session: AsyncSession, test_user):
    """Test max tokens validation."""
    with pytest.raises(GoalValidationError, match="Max tokens must be positive"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            priority=GoalPriority.MEDIUM,
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"],
                "keywords": ["test"]
            },
            max_tokens=Decimal("-1.0")  # Invalid value
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_threshold_validation(async_session: AsyncSession, test_user):
    """Test notification and auto-buy threshold validation."""
    with pytest.raises(GoalValidationError, match="Thresholds must be between 0 and 1"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            priority=GoalPriority.MEDIUM,
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"],
                "keywords": ["test"]
            },
            notification_threshold=1.5  # Invalid value
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_goal_user_relationship(async_session: AsyncSession, test_user):
    """Test goal-user relationship."""
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        priority=GoalPriority.MEDIUM,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"],
            "keywords": ["test"]
        }
    )
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    await async_session.refresh(test_user)
    
    assert goal.user == test_user
    assert goal in test_user.goals

@pytest.mark.asyncio
async def test_goal_timestamps(async_session: AsyncSession, test_user):
    """Test goal timestamps."""
    before_create = datetime.now(timezone.utc)
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        priority=GoalPriority.MEDIUM,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"],
            "keywords": ["test"]
        }
    )
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    after_create = datetime.now(timezone.utc)
    
    assert before_create <= goal.created_at <= after_create
    assert goal.created_at == goal.updated_at

@pytest.mark.asyncio
async def test_goal_priority_validation(async_session: AsyncSession, test_user):
    """Test goal priority validation."""
    with pytest.raises(ValueError, match="'invalid_priority' is not a valid GoalPriority"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"],
                "keywords": ["test"]
            },
            priority="invalid_priority"  # Invalid priority
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_goal_deadline_validation(async_session: AsyncSession, test_user):
    """Test goal deadline validation."""
    past_deadline = datetime.now(timezone.utc) - timedelta(days=1)
    with pytest.raises(GoalValidationError, match="Deadline must be in the future"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"],
                "keywords": ["test"]
            },
            deadline=past_deadline  # Past deadline
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_goal_constraints_schema(async_session: AsyncSession, test_user):
    """Test goal constraints schema validation."""
    with pytest.raises(GoalValidationError, match="Invalid constraints format"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            priority=GoalPriority.MEDIUM,
            constraints=["invalid", "format"]  # Invalid format
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_goal_completion_criteria(async_session: AsyncSession, test_user):
    """Test goal completion criteria."""
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        priority=GoalPriority.MEDIUM,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"],
            "keywords": ["test"]
        },
        max_matches=5
    )
    async_session.add(goal)
    await async_session.commit()
    
    # Simulate finding matches
    goal.matches_found = 5
    await goal.check_completion(async_session)
    await async_session.refresh(goal)
    
    assert goal.status == GoalStatus.COMPLETED

@pytest.mark.asyncio
async def test_goal_auto_expiration(test_user, async_session):
    """Test that goals are automatically marked as expired when deadline passes."""
    base_time = datetime(2025, 2, 22, 12, 0, tzinfo=timezone.utc)
    future_time = base_time + timedelta(seconds=2)

    # Patch datetime in both modules
    with patch('core.models.goal.datetime') as mock_datetime, \
         patch('datetime.datetime') as mock_datetime_global:
        # Configure mock datetime for goal creation
        mock_datetime.now.return_value = base_time
        mock_datetime.side_effect = datetime
        mock_datetime.timezone = timezone
        mock_datetime.timedelta = timedelta

        # Configure global datetime mock
        mock_datetime_global.now.return_value = base_time
        mock_datetime_global.side_effect = datetime
        mock_datetime_global.timezone = timezone
        mock_datetime_global.timedelta = timedelta

        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            constraints={
                "keywords": ["test"],
                "brands": ["Test"],
                "conditions": ["new"],
                "min_price": 500,
                "max_price": 1000
            },
            deadline=base_time + timedelta(seconds=1),
            created_at=base_time,
            updated_at=base_time
        )

        async_session.add(goal)
        await async_session.commit()
        await async_session.refresh(goal)

        initial_created_at = goal.created_at
        initial_updated_at = goal.updated_at

        # Move time forward
        mock_datetime.now.return_value = future_time
        mock_datetime_global.now.return_value = future_time

        # Check completion
        await goal.check_completion(async_session)

        # Verify goal is expired
        assert goal.status == GoalStatus.EXPIRED
        assert goal.created_at == initial_created_at
        assert goal.updated_at == future_time  # Should be exactly future_time since we're mocking datetime.now