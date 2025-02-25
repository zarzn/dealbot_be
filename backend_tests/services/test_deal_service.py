import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from core.services.deal import DealService
from core.services.redis import get_redis_service
from core.models.enums import DealStatus
from core.exceptions import DealError, ValidationError
from factories.user import UserFactory
from factories.deal import DealFactory
from factories.goal import GoalFactory
from factories.market import MarketFactory
from utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def deal_service(db_session):
    redis_service = await get_redis_service()
    return DealService(db_session, redis_service)

@service_test
@depends_on("core.test_models.test_deal.test_create_deal")
async def test_create_deal(db_session, deal_service):
    """Test creating a deal through the service."""
    user = await UserFactory.create_async(db_session=db_session)
    goal = await GoalFactory.create_async(db_session=db_session, user=user)
    market = await MarketFactory.create_async(db_session=db_session)
    
    deal_data = {
        "title": "Test Deal",
        "description": "Test Description",
        "url": "https://test.com/deal",
        "price": Decimal("99.99"),
        "original_price": Decimal("149.99"),
        "currency": "USD",
        "source": "manual",
        "image_url": "https://test.com/image.jpg",
        "category": "electronics",
        "seller_info": {
            "name": "Test Seller",
            "rating": 4.5,
            "reviews": 100
        }
    }
    
    deal = await deal_service.create_deal(
        user_id=user.id,
        goal_id=goal.id,
        market_id=market.id,
        **deal_data
    )
    
    assert deal.title == deal_data["title"]
    assert deal.price == deal_data["price"]
    assert deal.user_id == user.id
    assert deal.goal_id == goal.id
    assert deal.market_id == market.id
    assert deal.status == DealStatus.ACTIVE.value

@service_test
@depends_on("core.test_models.test_deal.test_create_deal")
async def test_get_deal(db_session, deal_service):
    """Test retrieving a deal."""
    deal = await DealFactory.create_async(db_session=db_session)
    
    # Get deal by ID
    retrieved_deal = await deal_service.get_deal(deal.id)
    assert retrieved_deal.id == deal.id
    
    # Test non-existent deal
    with pytest.raises(DealError):
        await deal_service.get_deal("non-existent-id")

@service_test
@depends_on("core.test_models.test_deal.test_create_deal")
async def test_update_deal(db_session, deal_service):
    """Test updating a deal."""
    deal = await DealFactory.create_async(db_session=db_session)
    
    # Update deal
    updates = {
        "title": "Updated Deal",
        "price": Decimal("89.99"),
        "status": DealStatus.EXPIRED.value
    }
    
    updated_deal = await deal_service.update_deal(
        deal.id,
        **updates
    )
    
    assert updated_deal.title == updates["title"]
    assert updated_deal.price == updates["price"]
    assert updated_deal.status == updates["status"]

@service_test
@depends_on("core.test_models.test_deal.test_create_deal")
async def test_list_deals(db_session, deal_service):
    """Test listing deals with filters."""
    user = await UserFactory.create_async(db_session=db_session)
    goal = await GoalFactory.create_async(db_session=db_session, user=user)
    
    # Create multiple deals
    deals = []
    for i in range(3):
        deal = await DealFactory.create_async(
            db_session=db_session,
            user=user,
            goal=goal,
            price=Decimal(f"{50 + i}.99")
        )
        deals.append(deal)
    
    # Test listing all deals
    all_deals = await deal_service.list_deals()
    assert len(all_deals) >= 3
    
    # Test filtering by user
    user_deals = await deal_service.list_deals(user_id=user.id)
    assert len(user_deals) == 3
    
    # Test filtering by goal
    goal_deals = await deal_service.list_deals(goal_id=goal.id)
    assert len(goal_deals) == 3
    
    # Test filtering by price range
    price_deals = await deal_service.list_deals(
        min_price=Decimal("50.00"),
        max_price=Decimal("51.99")
    )
    assert len(price_deals) == 2

@service_test
@depends_on("core.test_models.test_deal.test_create_deal")
async def test_delete_deal(db_session, deal_service):
    """Test deleting a deal."""
    deal = await DealFactory.create_async(db_session=db_session)
    
    # Delete deal
    await deal_service.delete_deal(deal.id)
    
    # Verify deal is deleted
    with pytest.raises(DealError):
        await deal_service.get_deal(deal.id)

@service_test
@depends_on("core.test_models.test_deal.test_create_deal")
async def test_validate_deal(db_session, deal_service):
    """Test deal validation."""
    # Test invalid price
    with pytest.raises(ValidationError):
        await deal_service.validate_deal_data({
            "price": Decimal("-10.00")
        })
    
    # Test invalid status
    with pytest.raises(ValidationError):
        await deal_service.validate_deal_data({
            "status": "invalid_status"
        })
    
    # Test valid data
    valid_data = {
        "price": Decimal("99.99"),
        "status": DealStatus.ACTIVE.value
    }
    validated_data = await deal_service.validate_deal_data(valid_data)
    assert validated_data == valid_data

@service_test
@depends_on("core.test_models.test_deal.test_create_deal")
async def test_deal_price_tracking(db_session, deal_service):
    """Test deal price tracking functionality."""
    deal = await DealFactory.create_async(db_session=db_session)
    
    # Add price point
    await deal_service.add_price_point(
        deal.id,
        price=Decimal("99.99"),
        source="test_source"
    )
    
    # Get price history
    history = await deal_service.get_price_history(deal.id)
    assert len(history) == 1
    assert history[0].price == Decimal("99.99")
    
    # Add another price point
    await deal_service.add_price_point(
        deal.id,
        price=Decimal("89.99"),
        source="test_source"
    )
    
    # Get updated history
    history = await deal_service.get_price_history(deal.id)
    assert len(history) == 2
    assert history[1].price == Decimal("89.99") 