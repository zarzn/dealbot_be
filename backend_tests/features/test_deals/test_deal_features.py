import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from core.services.deal import DealService
from core.services.goal import GoalService
from core.services.market import MarketService
from core.services.token import TokenService
from core.services.redis import get_redis_service
from core.models.enums import DealStatus, GoalStatus, MarketType
from core.exceptions import DealError, ValidationError
from factories.user import UserFactory
from factories.goal import GoalFactory
from factories.deal import DealFactory
from factories.market import MarketFactory
from utils.markers import feature_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def services(db_session):
    """Initialize all required services."""
    redis_service = await get_redis_service()
    return {
        'deal': DealService(db_session, redis_service),
        'goal': GoalService(db_session, redis_service),
        'market': MarketService(db_session, redis_service),
        'token': TokenService(db_session, redis_service)
    }

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
@depends_on("services.test_market_service.test_create_market")
async def test_deal_discovery_workflow(db_session, services):
    """Test complete deal discovery workflow."""
    # Create market
    market = await MarketFactory.create_async(
        db_session=db_session,
        type=MarketType.TEST.value,
        status='active'
    )
    
    # Create test product data
    product_data = {
        "title": "Gaming Laptop",
        "description": "High-end gaming laptop",
        "url": "https://test.com/laptop",
        "price": Decimal("999.99"),
        "original_price": Decimal("1299.99"),
        "currency": "USD",
        "category": "electronics"
    }
    
    # Discover deal from market
    deal = await services['deal'].discover_deal(
        market_id=market.id,
        product_data=product_data
    )
    
    assert deal.title == product_data["title"]
    assert deal.price == product_data["price"]
    assert deal.market_id == market.id
    assert deal.status == DealStatus.ACTIVE.value

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
async def test_deal_price_tracking_workflow(db_session, services):
    """Test deal price tracking workflow."""
    deal = await DealFactory.create_async(
        db_session=db_session,
        price=Decimal("100.0"),
        original_price=Decimal("150.0")
    )
    
    # Add price points
    price_points = [
        Decimal("100.0"),
        Decimal("95.0"),
        Decimal("90.0"),
        Decimal("85.0")
    ]
    
    for price in price_points:
        await services['deal'].add_price_point(
            deal_id=deal.id,
            price=price,
            source="test"
        )
    
    # Get price history
    history = await services['deal'].get_price_history(deal.id)
    assert len(history) == len(price_points)
    assert history[-1].price == price_points[-1]
    
    # Get price trends
    trends = await services['deal'].analyze_price_trends(deal.id)
    assert trends["trend"] == "decreasing"
    assert trends["lowest_price"] == Decimal("85.0")

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
@depends_on("services.test_goal_service.test_create_goal")
async def test_deal_matching_workflow(db_session, services):
    """Test deal matching with goals workflow."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create goal
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user=user,
        constraints={
            "price_range": {
                "min": 0,
                "max": 1000
            },
            "keywords": ["gaming", "laptop"],
            "categories": ["electronics"]
        }
    )
    
    # Create matching deal
    deal = await DealFactory.create_async(
        db_session=db_session,
        title="Gaming Laptop Deal",
        price=Decimal("899.99"),
        category="electronics"
    )
    
    # Match deal with goals
    matches = await services['deal'].match_with_goals(deal.id)
    assert len(matches) == 1
    assert matches[0].id == goal.id
    
    # Verify deal is linked to goal
    deal_goals = await services['deal'].get_matched_goals(deal.id)
    assert len(deal_goals) == 1
    assert deal_goals[0].id == goal.id

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
async def test_deal_expiration_workflow(db_session, services):
    """Test deal expiration workflow."""
    # Create deal with expiration
    deal = await DealFactory.create_async(
        db_session=db_session,
        expires_at=datetime.utcnow() - timedelta(hours=1)
    )
    
    # Check expired deals
    await services['deal'].check_expired_deals()
    
    # Verify deal status
    updated_deal = await services['deal'].get_deal(deal.id)
    assert updated_deal.status == DealStatus.EXPIRED.value

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
async def test_deal_validation_workflow(db_session, services):
    """Test deal validation workflow."""
    deal = await DealFactory.create_async(db_session=db_session)
    
    # Validate deal data
    validation_result = await services['deal'].validate_deal(
        deal.id,
        validate_url=True,
        validate_price=True
    )
    
    assert validation_result["is_valid"]
    assert validation_result["url_accessible"]
    assert validation_result["price_reasonable"]
    
    # Test invalid price validation
    with pytest.raises(ValidationError):
        await services['deal'].validate_deal_data({
            "price": Decimal("-10.0")
        })

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
@depends_on("services.test_market_service.test_create_market")
async def test_deal_refresh_workflow(db_session, services):
    """Test deal refresh workflow."""
    market = await MarketFactory.create_async(db_session=db_session)
    deal = await DealFactory.create_async(
        db_session=db_session,
        market=market,
        price=Decimal("100.0")
    )
    
    # Simulate market price change
    new_price = Decimal("90.0")
    await services['market'].update_product_price(
        market.id,
        deal.url,
        new_price
    )
    
    # Refresh deal
    updated_deal = await services['deal'].refresh_deal(deal.id)
    assert updated_deal.price == new_price
    
    # Verify price history
    history = await services['deal'].get_price_history(deal.id)
    assert len(history) == 2  # Original + updated price 