import pytest
import json
from decimal import Decimal
from datetime import datetime, timedelta
from httpx import AsyncClient
from websockets.client import connect as ws_connect
from core.models.enums import GoalStatus, DealStatus, MarketType
from core.services.auth import AuthService
from core.services.redis import get_redis_service
from factories.user import UserFactory
from factories.goal import GoalFactory
from factories.deal import DealFactory
from factories.market import MarketFactory
from factories.token import TokenTransactionFactory
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
@depends_on("features.test_goals.test_goal_creation_workflow")
@depends_on("features.test_deals.test_deal_discovery_workflow")
@depends_on("features.test_agents.test_notification_agent_workflow")
async def test_goal_to_deal_workflow(auth_data, db_session, client: AsyncClient):
    """Test complete workflow from goal creation to deal matching."""
    # Setup WebSocket connection for notifications
    async with ws_connect(
        f"ws://localhost:8000/api/v1/ws?token={auth_data['token']}"
    ) as websocket:
        # 1. Add tokens to user
        await TokenTransactionFactory.create_async(
            db_session=db_session,
            user_id=auth_data["user_id"],
            amount=Decimal("100.0")
        )
        
        # 2. Create goal
        goal_data = {
            "title": "Gaming Laptop",
            "item_category": "electronics",
            "constraints": {
                "price_range": {
                    "min": 800,
                    "max": 2000
                },
                "keywords": ["gaming", "laptop", "rtx"],
                "categories": ["electronics"]
            },
            "deadline": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "priority": 1,
            "max_matches": 5,
            "notification_threshold": "0.2",  # 20% discount
            "auto_buy_threshold": "0.3"  # 30% discount
        }
        
        response = await client.post(
            "/api/v1/goals",
            headers={"Authorization": f"Bearer {auth_data['token']}"},
            json=goal_data
        )
        assert response.status_code == 201
        goal_id = response.json()["id"]
        
        # 3. Create market and deals
        market = await MarketFactory.create_async(
            db_session=db_session,
            type=MarketType.TEST.value
        )
        
        # Create matching deal
        matching_deal_data = {
            "title": "RTX 3080 Gaming Laptop",
            "description": "High-end gaming laptop",
            "url": "https://test.com/laptop1",
            "price": "1599.99",
            "original_price": "1999.99",  # 20% discount
            "currency": "USD",
            "category": "electronics",
            "market_id": str(market.id)
        }
        
        response = await client.post(
            "/api/v1/deals",
            headers={"Authorization": f"Bearer {auth_data['token']}"},
            json=matching_deal_data
        )
        assert response.status_code == 201
        deal_id = response.json()["id"]
        
        # 4. Wait for deal match notification
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "deal_match"
        assert data["goal_id"] == goal_id
        assert data["deal_id"] == deal_id
        
        # 5. Update deal price to trigger auto-buy
        new_price = Decimal("1399.99")  # 30% discount
        response = await client.post(
            f"/api/v1/deals/{deal_id}/prices",
            headers={"Authorization": f"Bearer {auth_data['token']}"},
            json={
                "price": str(new_price),
                "source": "test"
            }
        )
        assert response.status_code == 201
        
        # 6. Wait for auto-buy notification
        message = await websocket.recv()
        data = json.loads(message)
        assert data["type"] == "auto_buy_triggered"
        assert data["goal_id"] == goal_id
        assert data["deal_id"] == deal_id
        
        # 7. Verify goal status
        response = await client.get(
            f"/api/v1/goals/{goal_id}",
            headers={"Authorization": f"Bearer {auth_data['token']}"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == GoalStatus.COMPLETED.value

@integration_test
@depends_on("features.test_deals.test_deal_price_tracking_workflow")
@depends_on("features.test_agents.test_price_prediction_workflow")
async def test_price_tracking_workflow(auth_data, db_session, client: AsyncClient):
    """Test complete price tracking and prediction workflow."""
    async with ws_connect(
        f"ws://localhost:8000/api/v1/ws?token={auth_data['token']}"
    ) as websocket:
        # 1. Create market and deal
        market = await MarketFactory.create_async(
            db_session=db_session,
            type=MarketType.TEST.value
        )
        
        deal_data = {
            "title": "Test Product",
            "url": "https://test.com/product",
            "price": "100.0",
            "market_id": str(market.id)
        }
        
        response = await client.post(
            "/api/v1/deals",
            headers={"Authorization": f"Bearer {auth_data['token']}"},
            json=deal_data
        )
        assert response.status_code == 201
        deal_id = response.json()["id"]
        
        # 2. Add price points over time
        price_points = [
            "100.0", "95.0", "90.0", "85.0", "80.0"
        ]
        
        for price in price_points:
            response = await client.post(
                f"/api/v1/deals/{deal_id}/prices",
                headers={"Authorization": f"Bearer {auth_data['token']}"},
                json={
                    "price": price,
                    "source": "test"
                }
            )
            assert response.status_code == 201
            
            # Wait for price update notification
            message = await websocket.recv()
            data = json.loads(message)
            assert data["type"] == "price_update"
            assert data["deal_id"] == deal_id
        
        # 3. Get price history
        response = await client.get(
            f"/api/v1/deals/{deal_id}/prices",
            headers={"Authorization": f"Bearer {auth_data['token']}"}
        )
        assert response.status_code == 200
        history = response.json()
        assert len(history["items"]) == len(price_points)
        
        # 4. Get price prediction
        response = await client.get(
            f"/api/v1/deals/{deal_id}/predict",
            headers={"Authorization": f"Bearer {auth_data['token']}"},
            params={"days": 7}
        )
        assert response.status_code == 200
        prediction = response.json()
        assert "predicted_prices" in prediction
        assert "confidence" in prediction
        assert len(prediction["predicted_prices"]) == 7

@integration_test
@depends_on("features.test_agents.test_market_search_workflow")
async def test_market_search_workflow(auth_data, db_session, client: AsyncClient):
    """Test complete market search workflow."""
    # 1. Create market
    market = await MarketFactory.create_async(
        db_session=db_session,
        type=MarketType.TEST.value
    )
    
    # 2. Search for products
    search_params = {
        "keywords": ["gaming", "laptop"],
        "price_range": {
            "min": 800,
            "max": 2000
        },
        "category": "electronics"
    }
    
    response = await client.post(
        f"/api/v1/markets/{market.id}/search",
        headers={"Authorization": f"Bearer {auth_data['token']}"},
        json=search_params
    )
    
    assert response.status_code == 200
    results = response.json()
    assert len(results["items"]) > 0
    
    # 3. Create deals from search results
    for result in results["items"][:2]:  # Create deals for first 2 results
        deal_data = {
            "title": result["title"],
            "url": result["url"],
            "price": str(result["price"]),
            "market_id": str(market.id)
        }
        
        response = await client.post(
            "/api/v1/deals",
            headers={"Authorization": f"Bearer {auth_data['token']}"},
            json=deal_data
        )
        assert response.status_code == 201
    
    # 4. Verify deals were created
    response = await client.get(
        "/api/v1/deals",
        headers={"Authorization": f"Bearer {auth_data['token']}"},
        params={"market_id": str(market.id)}
    )
    
    assert response.status_code == 200
    deals = response.json()
    assert len(deals["items"]) >= 2 