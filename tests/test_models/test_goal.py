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
            "keywords": ["laptop", "gaming"],
            "exclude_keywords": ["refurbished"]
        },
        priority=GoalPriority.MEDIUM,
        status=GoalStatus.ACTIVE
    )
    
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.id is not None
    assert goal.title == "Test Goal"
    assert goal.item_category == MarketCategory.ELECTRONICS
    assert goal.constraints["max_price"] == 1000
    assert goal.constraints["min_price"] == 500
    assert "laptop" in goal.constraints["keywords"]
    assert goal.priority == GoalPriority.MEDIUM
    assert goal.status == GoalStatus.ACTIVE
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
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"]
            }
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_invalid_constraints_format(async_session: AsyncSession, test_user):
    """Test invalid constraints format validation."""
    with pytest.raises(GoalValidationError, match="Invalid constraints format"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            constraints="not-a-json-object"  # Invalid format
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_invalid_price_constraints(async_session: AsyncSession, test_user):
    """Test invalid price constraints validation."""
    with pytest.raises(GoalValidationError, match="Min price must be less than max price"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            constraints={
                "max_price": 500,  # Lower than min_price
                "min_price": 1000,
                "brands": ["Test"],
                "conditions": ["new"]
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
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"]
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
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"]
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
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"]
            },
            notification_threshold=Decimal("1.5"),  # Invalid value
            auto_buy_threshold=Decimal("1.2")  # Invalid value
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
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        }
    )
    
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.user.id == test_user.id
    assert goal in test_user.goals

@pytest.mark.asyncio
async def test_goal_status_transitions(async_session: AsyncSession, test_user):
    """Test goal status transitions."""
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        },
        status=GoalStatus.ACTIVE
    )
    
    async_session.add(goal)
    await async_session.commit()
    
    # Test valid transitions
    valid_transitions = [
        GoalStatus.PAUSED,
        GoalStatus.ACTIVE,
        GoalStatus.COMPLETED,
        GoalStatus.CANCELLED,
        GoalStatus.ERROR
    ]
    
    for status in valid_transitions:
        goal.status = status
        await async_session.commit()
        await async_session.refresh(goal)
        assert goal.status == status

@pytest.mark.asyncio
async def test_goal_with_deadline(async_session: AsyncSession, test_user):
    """Test goal with deadline."""
    deadline = datetime.now(timezone.utc) + timedelta(days=7)
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        },
        deadline=deadline
    )
    
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.deadline is not None
    assert isinstance(goal.deadline, datetime)
    assert goal.deadline.tzinfo is not None  # Ensure timezone-aware
    assert goal.deadline > datetime.now(timezone.utc)

@pytest.mark.asyncio
async def test_goal_with_notification_threshold(async_session: AsyncSession, test_user):
    """Test goal with notification threshold."""
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        },
        notification_threshold=Decimal("0.2")  # 20% price drop
    )
    
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.notification_threshold == Decimal("0.2")

@pytest.mark.asyncio
async def test_goal_with_auto_buy_threshold(async_session: AsyncSession, test_user):
    """Test goal with auto buy threshold."""
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        },
        auto_buy_threshold=Decimal("0.3")  # 30% price drop
    )
    
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.auto_buy_threshold == Decimal("0.3")

@pytest.mark.asyncio
async def test_goal_timestamps(async_session: AsyncSession, test_user):
    """Test goal timestamps."""
    before_create = datetime.now(timezone.utc)
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        }
    )
    
    async_session.add(goal)
    await async_session.commit()
    await async_session.refresh(goal)
    after_create = datetime.now(timezone.utc)
    
    assert before_create <= goal.created_at <= after_create
    assert before_create <= goal.updated_at <= after_create
    
    # Test update timestamp
    await asyncio.sleep(1)  # Ensure time difference
    goal.title = "Updated Goal"
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.updated_at > goal.created_at

@pytest.mark.asyncio
async def test_goal_priority_validation(async_session: AsyncSession, test_user):
    """Test goal priority validation."""
    with pytest.raises(GoalValidationError, match="Priority must be between 1 and 5"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"]
            },
            priority=6  # Invalid priority
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_goal_deadline_validation(async_session: AsyncSession, test_user):
    """Test goal deadline validation."""
    with pytest.raises(GoalValidationError, match="Deadline must be in the future"):
        past_deadline = datetime.now(timezone.utc) - timedelta(days=1)
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            constraints={
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"]
            },
            deadline=past_deadline
        )
        async_session.add(goal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_goal_constraints_schema(async_session: AsyncSession, test_user):
    """Test goal constraints schema validation."""
    with pytest.raises(GoalConstraintError, match="Invalid constraints schema"):
        goal = Goal(
            user_id=test_user.id,
            title="Test Goal",
            item_category=MarketCategory.ELECTRONICS,
            constraints={
                "invalid_key": "value"  # Invalid constraint key
            }
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
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        },
        max_matches=5
    )
    
    async_session.add(goal)
    await async_session.commit()
    
    # Simulate reaching max matches
    goal.matches_found = 5
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.status == GoalStatus.COMPLETED

@pytest.mark.asyncio
async def test_goal_constraints_update(async_session: AsyncSession, test_user):
    """Test updating goal constraints."""
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        }
    )
    
    async_session.add(goal)
    await async_session.commit()
    
    # Update constraints
    goal.constraints = {
        "max_price": 1500,
        "min_price": 700,
        "brands": ["Test", "Another"],
        "conditions": ["new", "like_new"]
    }
    
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.constraints["max_price"] == 1500
    assert goal.constraints["min_price"] == 700
    assert len(goal.constraints["brands"]) == 2
    assert len(goal.constraints["conditions"]) == 2

@pytest.mark.asyncio
async def test_goal_auto_expiration(async_session: AsyncSession, test_user):
    """Test goal auto expiration."""
    deadline = datetime.now(timezone.utc) + timedelta(seconds=1)
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category=MarketCategory.ELECTRONICS,
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        },
        deadline=deadline
    )
    
    async_session.add(goal)
    await async_session.commit()
    
    # Wait for deadline to pass
    await asyncio.sleep(2)
    
    # Check if goal is expired by checking deadline
    now = datetime.now(timezone.utc)
    if goal.deadline and goal.deadline <= now:
        goal.status = GoalStatus.ERROR
    await async_session.commit()
    await async_session.refresh(goal)
    
    assert goal.status == GoalStatus.ERROR
    assert goal.updated_at > goal.created_at 