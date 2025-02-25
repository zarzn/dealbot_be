import pytest
from uuid import UUID
from decimal import Decimal
from sqlalchemy import select
from core.models.deal import Deal
from core.models.enums import DealStatus
from backend_tests.factories import UserFactory, GoalFactory, DealFactory, MarketFactory
from backend_tests.utils import core_test, depends_on

pytestmark = pytest.mark.asyncio

@core_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_create_deal(db_session):
    """Test creating a deal."""
    # Create required related objects
    user = await UserFactory.create_async(db_session=db_session)
    goal = await GoalFactory.create_async(db_session=db_session, user=user)
    market = await MarketFactory.create_async(db_session=db_session)
    
    # Create a deal
    deal = await DealFactory.create_async(
        db_session=db_session,
        user=user,
        goal=goal,
        market=market,
        title="Test Deal",
        price=Decimal("99.99"),
        status=DealStatus.ACTIVE.value
    )
    
    # Verify deal was created
    assert deal.id is not None
    assert isinstance(deal.id, UUID)
    assert deal.title == "Test Deal"
    assert deal.price == Decimal("99.99")
    assert deal.status == DealStatus.ACTIVE.value
    assert deal.user_id == user.id
    assert deal.goal_id == goal.id
    assert deal.market_id == market.id
    
    # Verify deal exists in database
    stmt = select(Deal).where(Deal.id == deal.id)
    result = await db_session.execute(stmt)
    db_deal = result.scalar_one()
    
    assert db_deal.id == deal.id
    assert db_deal.title == "Test Deal"
    assert db_deal.price == Decimal("99.99")
    assert db_deal.status == DealStatus.ACTIVE.value
    assert db_deal.user_id == user.id
    assert db_deal.goal_id == goal.id
    assert db_deal.market_id == market.id

@core_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_deal_price_validation(db_session):
    """Test deal price validation."""
    user = await UserFactory.create_async(db_session=db_session)
    goal = await GoalFactory.create_async(db_session=db_session, user=user)
    market = await MarketFactory.create_async(db_session=db_session)
    
    # Test negative price
    with pytest.raises(ValueError):
        await DealFactory.create_async(
            db_session=db_session,
            user=user,
            goal=goal,
            market=market,
            price=Decimal("-10.0")  # Negative price should fail
        )
    
    # Test zero price
    with pytest.raises(ValueError):
        await DealFactory.create_async(
            db_session=db_session,
            user=user,
            goal=goal,
            market=market,
            price=Decimal("0.0")  # Zero price should fail
        )
    
    # Test valid price
    deal = await DealFactory.create_async(
        db_session=db_session,
        user=user,
        goal=goal,
        market=market,
        price=Decimal("0.01")  # Minimum valid price
    )
    assert deal.price == Decimal("0.01")

@core_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_deal_status_transitions(db_session):
    """Test deal status transitions."""
    user = await UserFactory.create_async(db_session=db_session)
    goal = await GoalFactory.create_async(db_session=db_session, user=user)
    market = await MarketFactory.create_async(db_session=db_session)
    
    # Create deal with initial status
    deal = await DealFactory.create_async(
        db_session=db_session,
        user=user,
        goal=goal,
        market=market,
        status=DealStatus.ACTIVE.value
    )
    
    # Test valid status transition
    deal.status = DealStatus.EXPIRED.value
    await db_session.commit()
    await db_session.refresh(deal)
    assert deal.status == DealStatus.EXPIRED.value
    
    # Test invalid status
    with pytest.raises(ValueError):
        deal.status = "invalid_status"
        await db_session.commit()

@pytest.mark.asyncio
async def test_deal_relationships(db_session):
    """Test deal model relationships with user, goal, and market."""
    # Create test user, goal, and market
    user = await UserFactory.create_async(db_session=db_session)
    goal = await GoalFactory.create_async(db_session=db_session, user=user)
    market = await MarketFactory.create_async(db_session=db_session)
    
    deal = await DealFactory.create_async(
        db_session=db_session,
        user=user,
        goal=goal,
        market=market
    )
    
    # Test relationship with user
    assert deal.user == user
    
    # Refresh user to load deals relationship properly in async context
    await db_session.refresh(user, ["deals"])
    assert deal in user.deals
    
    # Test relationship with goal
    assert deal.goal == goal
    
    # Refresh goal to load deals relationship properly in async context
    await db_session.refresh(goal, ["deals"])
    assert deal in goal.deals
    
    # Test relationship with market
    assert deal.market == market
    
    # Refresh market to load deals relationship properly in async context
    await db_session.refresh(market, ["deals"])
    assert deal in market.deals
    
    # Test cascading delete from goal
    await db_session.delete(goal)
    await db_session.flush()
    
    # Verify deal is deleted when goal is deleted
    deal_check = await db_session.get(Deal, deal.id)
    assert deal_check is None 