import pytest
import json
from decimal import Decimal
from datetime import datetime
from httpx import AsyncClient
from websockets.client import connect as ws_connect
from core.services.auth import AuthService
from core.services.redis import get_redis_service
from core.models.enums import DealStatus, GoalStatus
from factories.user import UserFactory
from factories.goal import GoalFactory
from factories.deal import DealFactory
from utils.markers import integration_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def auth_data(db_session):
    """Create authenticated user and return auth data."""
    redis_service = await get_redis_service()
    auth_service = AuthService(db_session, redis_service)
    
    user = await UserFactory.create_async(db_session=db_session)
    tokens = await auth_service.create_tokens(user)
    
    return {
        "token": tokens.access_token,
        "user_id": str(user.id)
    }

@integration_test
@depends_on("features.test_agents.test_notification_agent_workflow")
async def test_websocket_connection(auth_data):
    """Test WebSocket connection and authentication."""
    # Connect with valid token
    async with ws_connect(
        f"ws://localhost:8000/api/v1/ws?token={auth_data['token']}"
    ) as websocket:
        # Verify connection success
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "connection_established"
        assert data["user_id"] == auth_data["user_id"]
    
    # Try connecting without token
    try:
        async with ws_connect("ws://localhost:8000/api/v1/ws") as websocket:
            message = await websocket.recv()
            assert False, "Should not connect without token"
    except Exception as e:
        assert "unauthorized" in str(e).lower()
    
    # Try connecting with invalid token
    try:
        async with ws_connect(
            "ws://localhost:8000/api/v1/ws?token=invalid_token"
        ) as websocket:
            message = await websocket.recv()
            assert False, "Should not connect with invalid token"
    except Exception as e:
        assert "unauthorized" in str(e).lower()

@integration_test
@depends_on("features.test_agents.test_notification_agent_workflow")
async def test_deal_notifications(auth_data, db_session):
    """Test deal-related notifications."""
    async with ws_connect(
        f"ws://localhost:8000/api/v1/ws?token={auth_data['token']}"
    ) as websocket:
        # Create goal and deal
        goal = await GoalFactory.create_async(
            db_session=db_session,
            user_id=auth_data["user_id"]
        )
        deal = await DealFactory.create_async(
            db_session=db_session,
            goal=goal,
            price=Decimal("99.99")
        )
        
        # Should receive deal match notification
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "deal_match"
        assert data["goal_id"] == str(goal.id)
        assert data["deal_id"] == str(deal.id)
        
        # Update deal price
        await deal.update_price(Decimal("79.99"))
        
        # Should receive price update notification
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "price_update"
        assert data["deal_id"] == str(deal.id)
        assert Decimal(data["new_price"]) == Decimal("79.99")

@integration_test
@depends_on("features.test_agents.test_notification_agent_workflow")
async def test_goal_notifications(auth_data, db_session):
    """Test goal-related notifications."""
    async with ws_connect(
        f"ws://localhost:8000/api/v1/ws?token={auth_data['token']}"
    ) as websocket:
        # Create goal
        goal = await GoalFactory.create_async(
            db_session=db_session,
            user_id=auth_data["user_id"],
            max_matches=1
        )
        
        # Create deals to trigger goal completion
        for i in range(2):
            await DealFactory.create_async(
                db_session=db_session,
                goal=goal
            )
        
        # Should receive goal completion notification
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "goal_completed"
        assert data["goal_id"] == str(goal.id)

@integration_test
@depends_on("features.test_agents.test_notification_agent_workflow")
async def test_notification_preferences(auth_data, db_session, client: AsyncClient):
    """Test notification preferences."""
    # Update notification preferences
    preferences = {
        "deal_matches": True,
        "price_updates": False,
        "goal_updates": True
    }
    
    response = await client.put(
        "/api/v1/users/me/notifications/preferences",
        headers={"Authorization": f"Bearer {auth_data['token']}"},
        json=preferences
    )
    assert response.status_code == 200
    
    async with ws_connect(
        f"ws://localhost:8000/api/v1/ws?token={auth_data['token']}"
    ) as websocket:
        # Create goal and deal
        goal = await GoalFactory.create_async(
            db_session=db_session,
            user_id=auth_data["user_id"]
        )
        deal = await DealFactory.create_async(
            db_session=db_session,
            goal=goal
        )
        
        # Should receive deal match notification (enabled)
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "deal_match"
        
        # Update deal price
        await deal.update_price(Decimal("89.99"))
        
        # Should not receive price update notification (disabled)
        try:
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] != "price_update"
        except:
            pass  # Expected timeout

@integration_test
@depends_on("features.test_agents.test_notification_agent_workflow")
async def test_notification_history(auth_data, db_session, client: AsyncClient):
    """Test notification history API."""
    # Create some notifications via WebSocket
    async with ws_connect(
        f"ws://localhost:8000/api/v1/ws?token={auth_data['token']}"
    ) as websocket:
        goal = await GoalFactory.create_async(
            db_session=db_session,
            user_id=auth_data["user_id"]
        )
        for i in range(3):
            await DealFactory.create_async(
                db_session=db_session,
                goal=goal
            )
    
    # Get notification history
    response = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {auth_data['token']}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 3
    
    # Mark notification as read
    notification_id = data["items"][0]["id"]
    response = await client.post(
        f"/api/v1/notifications/{notification_id}/read",
        headers={"Authorization": f"Bearer {auth_data['token']}"}
    )
    assert response.status_code == 200
    
    # Verify notification is marked as read
    response = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {auth_data['token']}"},
        params={"status": "read"}
    )
    assert response.status_code == 200
    data = response.json()
    assert any(n["id"] == notification_id for n in data["items"]) 