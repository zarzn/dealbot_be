import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from httpx import AsyncClient
from core.models.enums import DealStatus, MarketType
from core.services.auth import AuthService
from core.services.redis import get_redis_service
from factories.user import UserFactory
from factories.goal import GoalFactory
from factories.deal import DealFactory
from factories.market import MarketFactory
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
@depends_on("features.test_deals.test_deal_discovery_workflow")
async def test_create_deal_api(client: AsyncClient, auth_headers, db_session):
    """Test deal creation API endpoint."""
    # Create required related objects
    market = await MarketFactory.create_async(
        db_session=db_session,
        type=MarketType.TEST.value
    )
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"]
    )
    
    # Create deal
    deal_data = {
        "title": "Test Deal",
        "description": "Test Description",
        "url": "https://test.com/deal",
        "price": "99.99",
        "original_price": "149.99",
        "currency": "USD",
        "source": "test_source",
        "image_url": "https://test.com/image.jpg",
        "category": "electronics",
        "market_id": str(market.id),
        "goal_id": str(goal.id)
    }
    
    response = await client.post(
        "/api/v1/deals",
        headers=auth_headers,
        json=deal_data
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == deal_data["title"]
    assert data["status"] == DealStatus.ACTIVE.value
    assert data["market_id"] == deal_data["market_id"]
    assert data["goal_id"] == deal_data["goal_id"]

@integration_test
@depends_on("features.test_deals.test_deal_price_tracking_workflow")
async def test_deal_price_history_api(client: AsyncClient, auth_headers, db_session):
    """Test deal price history API endpoints."""
    deal = await DealFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"]
    )
    
    # Add price points
    price_points = [
        Decimal("100.0"),
        Decimal("95.0"),
        Decimal("90.0")
    ]
    
    for price in price_points:
        response = await client.post(
            f"/api/v1/deals/{deal.id}/prices",
            headers=auth_headers,
            json={
                "price": str(price),
                "source": "test"
            }
        )
        assert response.status_code == 201
    
    # Get price history
    response = await client.get(
        f"/api/v1/deals/{deal.id}/prices",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert Decimal(data["items"][-1]["price"]) == Decimal("90.0")

@integration_test
@depends_on("features.test_deals.test_deal_matching_workflow")
async def test_list_deals_api(client: AsyncClient, auth_headers, db_session):
    """Test deal listing API endpoint."""
    # Create multiple deals
    deals = []
    for i in range(3):
        deal = await DealFactory.create_async(
            db_session=db_session,
            user_id=auth_headers["user_id"],
            price=Decimal(f"{50 + i*10}.99")
        )
        deals.append(deal)
    
    # List all deals
    response = await client.get(
        "/api/v1/deals",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    
    # Test pagination
    response = await client.get(
        "/api/v1/deals?page=1&size=2",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    
    # Test filtering by price range
    response = await client.get(
        "/api/v1/deals?min_price=50&max_price=60",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert all(50 <= Decimal(d["price"]) <= 60 for d in data["items"])

@integration_test
@depends_on("features.test_deals.test_deal_validation_workflow")
async def test_validate_deal_api(client: AsyncClient, auth_headers, db_session):
    """Test deal validation API endpoint."""
    deal = await DealFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"]
    )
    
    # Validate deal
    response = await client.post(
        f"/api/v1/deals/{deal.id}/validate",
        headers=auth_headers,
        json={
            "validate_url": True,
            "validate_price": True
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"]
    assert data["url_accessible"]
    assert data["price_reasonable"]

@integration_test
@depends_on("features.test_deals.test_deal_refresh_workflow")
async def test_refresh_deal_api(client: AsyncClient, auth_headers, db_session):
    """Test deal refresh API endpoint."""
    market = await MarketFactory.create_async(db_session=db_session)
    deal = await DealFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"],
        market=market,
        price=Decimal("100.0")
    )
    
    # Refresh deal
    response = await client.post(
        f"/api/v1/deals/{deal.id}/refresh",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "price" in data
    assert "last_checked_at" in data

@integration_test
@depends_on("features.test_deals.test_deal_matching_workflow")
async def test_deal_goals_api(client: AsyncClient, auth_headers, db_session):
    """Test deal goals API endpoints."""
    deal = await DealFactory.create_async(
        db_session=db_session,
        user_id=auth_headers["user_id"]
    )
    
    # Create goals
    goals = []
    for i in range(3):
        goal = await GoalFactory.create_async(
            db_session=db_session,
            user_id=auth_headers["user_id"]
        )
        goals.append(goal)
    
    # Match deal with goals
    response = await client.post(
        f"/api/v1/deals/{deal.id}/match",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "matches" in data
    
    # List matched goals
    response = await client.get(
        f"/api/v1/deals/{deal.id}/goals",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data 