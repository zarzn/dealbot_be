import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from httpx import AsyncClient
from core.models.enums import GoalStatus
from core.services.auth import AuthService
from core.services.redis import get_redis_service
from factories.user import UserFactory
from factories.goal import GoalFactory
from factories.deal import DealFactory
from factories.token import TokenTransactionFactory
from utils.markers import integration_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def auth_headers(db_session):
    """Create authenticated user and return auth headers."""
    redis_service = await get_redis_service()
    auth_service = AuthService(db_session, redis_service)
    
    user = await UserFactory.create_async(db_session=db_session)
    tokens = await auth_service.create_tokens(user)
    
    return {
        "Authorization": f"Bearer {tokens.access_token}",
        "user_id": str(user.id)
    }

@integration_test
@depends_on("features.test_goals.test_goal_creation_workflow")
async def test_create_goal_api(client: AsyncClient, auth_headers, db_session):
    """Test goal creation API endpoint."""
    # Add tokens to user
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"],
        amount=Decimal("100.0")
    )
    
    # Create goal
    goal_data = {
        "title": "Test Goal",
        "item_category": "electronics",
        "constraints": {
            "price_range": {
                "min": 0,
                "max": 1000
            },
            "keywords": ["test", "goal"],
            "categories": ["electronics"]
        },
        "deadline": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "priority": 1,
        "max_matches": 10,
        "max_tokens": "50.0",
        "notification_threshold": "0.8",
        "auto_buy_threshold": "0.9"
    }
    
    response = await client.post(
        "/api/v1/goals",
        headers=auth_headers,
        json=goal_data
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == goal_data["title"]
    assert data["status"] == GoalStatus.ACTIVE.value
    
    # Verify token deduction
    balance_response = await client.get(
        "/api/v1/token/balance",
        headers=auth_headers
    )
    assert balance_response.status_code == 200
    assert Decimal(balance_response.json()["balance"]) < Decimal("100.0")

@integration_test
@depends_on("features.test_goals.test_goal_matching_workflow")
async def test_list_goals_api(client: AsyncClient, auth_headers, db_session):
    """Test goal listing API endpoint."""
    # Create multiple goals
    user_id = auth_headers["user_id"]
    goals = []
    for i in range(3):
        goal = await GoalFactory.create_async(
            db_session=db_session,
            user_id=user_id,
            priority=i + 1
        )
        goals.append(goal)
    
    # List all goals
    response = await client.get(
        "/api/v1/goals",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    
    # Test pagination
    response = await client.get(
        "/api/v1/goals?page=1&size=2",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    
    # Test filtering
    response = await client.get(
        f"/api/v1/goals?status={GoalStatus.ACTIVE.value}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert all(g["status"] == GoalStatus.ACTIVE.value for g in data["items"])

@integration_test
@depends_on("features.test_goals.test_goal_matching_workflow")
async def test_get_goal_api(client: AsyncClient, auth_headers, db_session):
    """Test goal retrieval API endpoint."""
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"]
    )
    
    # Get goal by ID
    response = await client.get(
        f"/api/v1/goals/{goal.id}",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(goal.id)
    
    # Test non-existent goal
    response = await client.get(
        "/api/v1/goals/non-existent-id",
        headers=auth_headers
    )
    assert response.status_code == 404

@integration_test
@depends_on("features.test_goals.test_goal_matching_workflow")
async def test_update_goal_api(client: AsyncClient, auth_headers, db_session):
    """Test goal update API endpoint."""
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"]
    )
    
    # Update goal
    updates = {
        "title": "Updated Goal",
        "priority": 2,
        "status": GoalStatus.PAUSED.value
    }
    
    response = await client.put(
        f"/api/v1/goals/{goal.id}",
        headers=auth_headers,
        json=updates
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == updates["title"]
    assert data["priority"] == updates["priority"]
    assert data["status"] == updates["status"]

@integration_test
@depends_on("features.test_goals.test_goal_matching_workflow")
async def test_delete_goal_api(client: AsyncClient, auth_headers, db_session):
    """Test goal deletion API endpoint."""
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"]
    )
    
    # Delete goal
    response = await client.delete(
        f"/api/v1/goals/{goal.id}",
        headers=auth_headers
    )
    
    assert response.status_code == 204
    
    # Verify goal is deleted
    response = await client.get(
        f"/api/v1/goals/{goal.id}",
        headers=auth_headers
    )
    assert response.status_code == 404

@integration_test
@depends_on("features.test_goals.test_goal_matching_workflow")
async def test_goal_deals_api(client: AsyncClient, auth_headers, db_session):
    """Test goal deals API endpoints."""
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"]
    )
    
    # Create deals for goal
    deals = []
    for i in range(3):
        deal = await DealFactory.create_async(
            db_session=db_session,
            goal=goal
        )
        deals.append(deal)
    
    # List goal deals
    response = await client.get(
        f"/api/v1/goals/{goal.id}/deals",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    
    # Test deal matching
    response = await client.post(
        f"/api/v1/goals/{goal.id}/match",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "matches" in data
    assert len(data["matches"]) > 0 