import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from core.services.goal import GoalService
from core.services.redis import get_redis_service
from core.models.enums import GoalStatus, GoalPriority, MarketType
from core.exceptions import GoalError, ValidationError
from backend_tests.factories.user import UserFactory
from backend_tests.factories.goal import GoalFactory
from backend_tests.utils.markers import service_test, depends_on
from backend_tests.mocks.redis_service_mock import get_redis_service_mock

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def goal_service(db_session):
    # Use our mocked Redis service
    redis_service = await get_redis_service_mock()
    return GoalService(db_session, redis_service)

@service_test
@depends_on("core.test_models.test_goal.test_create_goal")
async def test_create_goal(db_session, goal_service):
    """Test creating a goal through the service."""
    user = await UserFactory.create_async(db_session=db_session)
    
    goal_data = {
        "title": "Test Goal",
        "item_category": "electronics",
        "constraints": {
            "price_range": {
                "min": 0,
                "max": 1000
            },
            "min_price": 0,
            "max_price": 1000,
            "keywords": ["test", "goal"],
            "categories": ["electronics"],
            "brands": ["apple", "samsung"],
            "conditions": ["new", "refurbished"]
        },
        "deadline": datetime.now(timezone.utc) + timedelta(days=30),
        "priority": 1,
        "max_matches": 10,
        "max_tokens": Decimal("100.0"),
        "notification_threshold": Decimal("0.8"),
        "auto_buy_threshold": Decimal("0.9")
    }
    
    goal = await goal_service.create_goal(
        user_id=user.id,
        **goal_data
    )
    
    assert goal.title == goal_data["title"]
    assert goal.item_category == goal_data["item_category"]
    assert goal.constraints == goal_data["constraints"]
    assert goal.user_id == user.id
    assert goal.status == GoalStatus.ACTIVE.value

@service_test
@depends_on("core.test_models.test_goal.test_create_goal")
async def test_get_goal(db_session, goal_service):
    """Test retrieving a goal."""
    goal = await GoalFactory.create_async(db_session=db_session)
    
    # Get goal by ID
    retrieved_goal = await goal_service.get_goal(goal.id)
    assert retrieved_goal.id == goal.id
    
    # Test non-existent goal
    with pytest.raises(GoalError):
        await goal_service.get_goal("non-existent-id")

@service_test
@depends_on("core.test_models.test_goal.test_create_goal")
async def test_update_goal(db_session, goal_service):
    """Test updating a goal."""
    goal = await GoalFactory.create_async(db_session=db_session)
    
    # Update goal - title and status
    updates = {
        "title": "Updated Goal",
        "status": GoalStatus.PAUSED.value
    }
    
    updated_goal = await goal_service.update_goal(
        goal.id,
        **updates
    )
    
    assert updated_goal.title == updates["title"]
    assert updated_goal.status == updates["status"]

@service_test
@depends_on("core.test_models.test_goal.test_create_goal")
async def test_list_goals(db_session, goal_service):
    """Test listing goals with filters."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create multiple goals with different priorities
    goals = []
    priorities = [GoalPriority.HIGH, GoalPriority.MEDIUM, GoalPriority.LOW]
    for i in range(3):
        goal = await GoalFactory.create_async(
            db_session=db_session,
            user=user,
            priority=priorities[i].value,
            title=f"Goal for item {i}"  # Add unique suffix to title
        )
        goals.append(goal)
    
    # Test listing all goals
    all_goals = await goal_service.list_goals()
    assert len(all_goals) >= 3
    
    # Test filtering by user
    user_goals = await goal_service.list_goals(user_id=user.id)
    assert len(user_goals) == 3
    
    # Test filtering by status
    active_goals = await goal_service.list_goals(
        status=GoalStatus.ACTIVE
    )
    assert len(active_goals) >= 3
    
    # Test filtering by priority
    medium_and_low_priority_goals = await goal_service.list_goals(
        min_priority=2
    )
    assert len(medium_and_low_priority_goals) == 2

@service_test
@depends_on("core.test_models.test_goal.test_create_goal")
async def test_get_active_goals(db_session, goal_service):
    """Test retrieving active goals for monitoring."""
    # Create some goals with different statuses
    active_goal1 = await GoalFactory.create_async(
        db_session=db_session,
        status=GoalStatus.ACTIVE.value
    )
    
    active_goal2 = await GoalFactory.create_async(
        db_session=db_session,
        status=GoalStatus.ACTIVE.value
    )
    
    paused_goal = await GoalFactory.create_async(
        db_session=db_session,
        status=GoalStatus.PAUSED.value
    )
    
    # Get active goals
    active_goals = await goal_service.list_goals(
        status=GoalStatus.ACTIVE,
    )
    
    # Verify only active goals are returned
    active_goal_ids = [g.id for g in active_goals]
    assert active_goal1.id in active_goal_ids
    assert active_goal2.id in active_goal_ids
    assert paused_goal.id not in active_goal_ids

@service_test
@depends_on("core.test_models.test_goal.test_create_goal")
async def test_delete_goal(db_session, goal_service):
    """Test deleting a goal."""
    goal = await GoalFactory.create_async(db_session=db_session)
    
    # Delete goal
    await goal_service.delete_goal(goal.id)
    
    # Verify goal is deleted
    with pytest.raises(GoalError):
        await goal_service.get_goal(goal.id)

@service_test
@depends_on("core.test_models.test_goal.test_create_goal")
async def test_validate_goal(db_session, goal_service):
    """Test goal validation."""
    # Test invalid priority
    with pytest.raises(ValidationError):
        await goal_service.validate_goal_data({
            "priority": 0
        })
    
    # Test invalid status
    with pytest.raises(ValidationError):
        await goal_service.validate_goal_data({
            "status": "invalid_status"
        })
    
    # Test valid data
    valid_data = {
        "priority": 1,
        "status": GoalStatus.ACTIVE.value,
        "max_matches": 10
    }
    validated_data = await goal_service.validate_goal_data(valid_data)
    assert validated_data == valid_data

@service_test
@depends_on("core.test_models.test_goal.test_create_goal")
async def test_goal_constraints_validation(db_session, goal_service):
    """Test goal constraints validation."""
    # Test invalid price range
    with pytest.raises(ValidationError):
        await goal_service.validate_constraints({
            "price_range": {
                "min": 100,
                "max": 50  # max < min
            }
        })
    
    # Test missing required fields
    with pytest.raises(ValidationError):
        await goal_service.validate_constraints({
            "keywords": []  # Empty keywords
        })
    
    # Test valid constraints
    valid_constraints = {
        "price_range": {
            "min": 0,
            "max": 1000
        },
        "keywords": ["test", "goal"],
        "categories": ["electronics"]
    }
    validated_constraints = await goal_service.validate_constraints(valid_constraints)
    assert validated_constraints == valid_constraints 