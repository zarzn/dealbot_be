import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from core.services.agent import AgentService
from core.services.goal import GoalService
from core.services.deal import DealService
from core.services.market import MarketService
from core.services.redis import get_redis_service
from core.models.enums import GoalStatus, DealStatus, MarketType
from core.exceptions import AgentError
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
        'agent': AgentService(db_session, redis_service),
        'goal': GoalService(db_session, redis_service),
        'deal': DealService(db_session, redis_service),
        'market': MarketService(db_session, redis_service)
    }

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
async def test_goal_analysis_workflow(db_session, services):
    """Test goal analysis workflow."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create goal with natural language description
    goal_data = {
        "title": "Gaming Setup",
        "description": "Looking for a high-end gaming laptop with RTX 3080, "
                      "32GB RAM, and at least 1TB SSD. Budget is $2000. "
                      "Also interested in gaming mouse and mechanical keyboard.",
        "item_category": "electronics"
    }
    
    # Analyze goal
    analysis = await services['agent'].analyze_goal(goal_data)
    
    assert "keywords" in analysis
    assert "price_range" in analysis
    assert "categories" in analysis
    assert analysis["price_range"]["max"] <= 2000
    assert "gaming" in analysis["keywords"]
    assert "laptop" in analysis["keywords"]
    assert "electronics" in analysis["categories"]

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
async def test_deal_analysis_workflow(db_session, services):
    """Test deal analysis workflow."""
    deal = await DealFactory.create_async(
        db_session=db_session,
        title="Gaming Laptop RTX 3080",
        description="High-end gaming laptop with NVIDIA RTX 3080, "
                   "32GB RAM, 1TB SSD, and 165Hz display",
        price=Decimal("1799.99"),
        original_price=Decimal("2199.99")
    )
    
    # Analyze deal
    analysis = await services['agent'].analyze_deal(deal.id)
    
    assert "features" in analysis
    assert "value_score" in analysis
    assert "market_comparison" in analysis
    assert analysis["value_score"] > 0.8  # Good value (18% discount)
    assert "rtx 3080" in [f.lower() for f in analysis["features"]]

@feature_test
@depends_on("services.test_market_service.test_create_market")
async def test_market_search_workflow(db_session, services):
    """Test market search workflow."""
    market = await MarketFactory.create_async(
        db_session=db_session,
        type=MarketType.TEST.value
    )
    
    # Create search parameters
    search_params = {
        "keywords": ["gaming", "laptop", "rtx 3080"],
        "price_range": {
            "min": 1500,
            "max": 2500
        },
        "category": "electronics"
    }
    
    # Perform market search
    results = await services['agent'].search_market(
        market_id=market.id,
        search_params=search_params
    )
    
    assert len(results) > 0
    for result in results:
        assert result["price"] >= 1500
        assert result["price"] <= 2500
        assert "gaming" in result["title"].lower()

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
async def test_price_prediction_workflow(db_session, services):
    """Test price prediction workflow."""
    deal = await DealFactory.create_async(db_session=db_session)
    
    # Add historical price points
    price_points = [
        (datetime.utcnow() - timedelta(days=i), Decimal(f"{100 - i*5}.00"))
        for i in range(10)
    ]
    
    for date, price in price_points:
        await services['deal'].add_price_point(
            deal.id,
            price=price,
            source="test",
            timestamp=date
        )
    
    # Generate price prediction
    prediction = await services['agent'].predict_price(
        deal_id=deal.id,
        days=7
    )
    
    assert "predicted_prices" in prediction
    assert "confidence" in prediction
    assert "trend" in prediction
    assert len(prediction["predicted_prices"]) == 7
    assert prediction["confidence"] > 0.7

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
@depends_on("services.test_deal_service.test_create_deal")
async def test_deal_matching_agent_workflow(db_session, services):
    """Test deal matching agent workflow."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create goal
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user=user,
        title="Gaming Laptop",
        description="Looking for a gaming laptop with good graphics card"
    )
    
    # Create potential deals
    deals = []
    for i in range(3):
        deal = await DealFactory.create_async(
            db_session=db_session,
            title=f"Gaming Laptop {i+1}",
            description=f"Gaming laptop with RTX {3070 + i*10}",
            price=Decimal(f"{1500 + i*200}.00")
        )
        deals.append(deal)
    
    # Run matching agent
    matches = await services['agent'].find_matches(goal.id)
    
    assert len(matches) > 0
    for match in matches:
        assert match["score"] > 0.5
        assert match["reasons"]  # Explanation for match

@feature_test
@depends_on("services.test_deal_service.test_create_deal")
async def test_deal_validation_agent_workflow(db_session, services):
    """Test deal validation agent workflow."""
    deal = await DealFactory.create_async(
        db_session=db_session,
        title="Gaming Laptop",
        price=Decimal("999.99"),
        original_price=Decimal("1999.99")  # 50% discount
    )
    
    # Validate deal
    validation = await services['agent'].validate_deal(deal.id)
    
    assert "is_valid" in validation
    assert "confidence" in validation
    assert "checks" in validation
    assert validation["is_valid"] is False  # Too good to be true
    assert "suspicious_discount" in validation["checks"]

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
async def test_notification_agent_workflow(db_session, services):
    """Test notification agent workflow."""
    user = await UserFactory.create_async(db_session=db_session)
    goal = await GoalFactory.create_async(db_session=db_session, user=user)
    deal = await DealFactory.create_async(db_session=db_session)
    
    # Generate notification
    notification = await services['agent'].generate_notification(
        user_id=user.id,
        goal_id=goal.id,
        deal_id=deal.id,
        event_type="deal_match"
    )
    
    assert "title" in notification
    assert "message" in notification
    assert "priority" in notification
    assert "actions" in notification
    assert len(notification["message"]) > 0 