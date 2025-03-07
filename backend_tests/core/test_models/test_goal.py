import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.goal import Goal
from core.models.user import User
from core.models.enums import GoalStatus, GoalPriority

@pytest.mark.asyncio
async def test_create_goal(db_session: AsyncSession):
    """Test creating a goal in the database."""
    # Create a user first
    user = User(
        id=str(uuid.uuid4()),
        email="test_goal_user@example.com",
        username="test_goal_user",
        password_hash="hashed_password",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.flush()

    # Create a goal with all required fields
    goal_id = str(uuid.uuid4())
    goal = Goal(
        id=goal_id,
        user_id=user.id,
        title="Test Goal",
        description="This is a test goal",
        status=GoalStatus.ACTIVE.value,
        priority=GoalPriority.MEDIUM.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        constraints={
            "min_price": 100.0,
            "max_price": 500.0,
            "conditions": ["new", "like_new"],
            "brands": ["brand1", "brand2"]
        }
    )
    db_session.add(goal)
    await db_session.commit()

    # Query the goal to verify it was created
    result = await db_session.execute(select(Goal).where(Goal.id == goal_id))
    db_goal = result.scalars().first()

    assert db_goal is not None
    assert db_goal.id == goal_id
    assert db_goal.user_id == user.id
    assert db_goal.title == "Test Goal"
    assert db_goal.description == "This is a test goal"
    assert db_goal.status == GoalStatus.ACTIVE.value
    assert db_goal.priority == GoalPriority.MEDIUM.value
    assert db_goal.constraints["min_price"] == 100.0
    assert db_goal.constraints["max_price"] == 500.0
    assert "conditions" in db_goal.constraints
    assert "brands" in db_goal.constraints

@pytest.mark.asyncio
async def test_update_goal(db_session: AsyncSession):
    """Test updating a goal in the database."""
    # Create a user first
    user = User(
        id=str(uuid.uuid4()),
        email="test_goal_update@example.com",
        username="test_goal_update",
        password_hash="hashed_password",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.flush()

    # Create a goal with all required fields
    goal_id = str(uuid.uuid4())
    goal = Goal(
        id=goal_id,
        user_id=user.id,
        title="Original Goal",
        description="This is the original goal",
        status=GoalStatus.ACTIVE.value,
        priority=GoalPriority.LOW.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        constraints={
            "min_price": 50.0,
            "max_price": 200.0,
            "conditions": ["new"],
            "brands": ["brandA", "brandB"]
        }
    )
    db_session.add(goal)
    await db_session.commit()

    # Update the goal
    result = await db_session.execute(select(Goal).where(Goal.id == goal_id))
    db_goal = result.scalars().first()
    
    db_goal.title = "Updated Goal"
    db_goal.status = GoalStatus.COMPLETED.value
    db_goal.constraints = {
        "min_price": 75.0,
        "max_price": 300.0,
        "conditions": ["new", "refurbished"],
        "brands": ["brandA", "brandC"]
    }
    db_goal.updated_at = datetime.utcnow()
    
    await db_session.commit()

    # Query the goal to verify it was updated
    result = await db_session.execute(select(Goal).where(Goal.id == goal_id))
    updated_goal = result.scalars().first()

    assert updated_goal is not None
    assert updated_goal.title == "Updated Goal"
    assert updated_goal.status == GoalStatus.COMPLETED.value
    assert updated_goal.constraints["min_price"] == 75.0
    assert updated_goal.constraints["max_price"] == 300.0
    assert "refurbished" in updated_goal.constraints["conditions"]
    assert "brandC" in updated_goal.constraints["brands"]

@pytest.mark.asyncio
async def test_delete_goal(db_session: AsyncSession):
    """Test deleting a goal from the database."""
    # Create a user first
    user = User(
        id=str(uuid.uuid4()),
        email="test_goal_delete@example.com",
        username="test_goal_delete",
        password_hash="hashed_password",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.flush()

    # Create a goal
    goal_id = str(uuid.uuid4())
    goal = Goal(
        id=goal_id,
        user_id=user.id,
        title="Goal to Delete",
        description="This goal will be deleted",
        status=GoalStatus.ACTIVE.value,
        priority=GoalPriority.HIGH.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        constraints={
            "min_price": 100.0,
            "max_price": 500.0,
            "conditions": ["new"],
            "brands": ["brand1"]
        }
    )
    db_session.add(goal)
    await db_session.commit()

    # Delete the goal
    result = await db_session.execute(select(Goal).where(Goal.id == goal_id))
    db_goal = result.scalars().first()
    await db_session.delete(db_goal)
    await db_session.commit()

    # Verify the goal was deleted
    result = await db_session.execute(select(Goal).where(Goal.id == goal_id))
    deleted_goal = result.scalars().first()
    assert deleted_goal is None 