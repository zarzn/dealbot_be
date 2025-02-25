import pytest
from uuid import UUID
from sqlalchemy import select
from core.models.goal import Goal
from core.models.enums import GoalStatus
from factories.user import UserFactory
from factories.goal import GoalFactory
from utils.markers import feature_test, depends_on

pytestmark = pytest.mark.asyncio

@feature_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_create_goal(db_session):
    """Test creating a goal."""
    # Create a user first
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create a goal
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user=user,
        title="Test Goal",
        status=GoalStatus.ACTIVE.value
    )
    
    # Verify goal was created
    assert goal.id is not None
    assert isinstance(goal.id, UUID)
    assert goal.title == "Test Goal"
    assert goal.status == GoalStatus.ACTIVE.value
    assert goal.user_id == user.id
    
    # Verify goal exists in database
    stmt = select(Goal).where(Goal.id == goal.id)
    result = await db_session.execute(stmt)
    db_goal = result.scalar_one()
    
    assert db_goal.id == goal.id
    assert db_goal.title == "Test Goal"
    assert db_goal.status == GoalStatus.ACTIVE.value
    assert db_goal.user_id == user.id 