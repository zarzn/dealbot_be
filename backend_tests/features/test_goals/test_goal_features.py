import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from core.services.goal import GoalService
from core.services.deal import DealService
from core.services.token import TokenService
from core.services.redis import get_redis_service
from core.models.enums import GoalStatus, DealStatus
from core.exceptions import GoalError, InsufficientBalanceError
from factories.user import UserFactory
from factories.goal import GoalFactory
from factories.deal import DealFactory
from factories.token import TokenTransactionFactory
from utils.markers import feature_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def services(db_session):
    """Initialize all required services."""
    redis_service = await get_redis_service()
    return {
        'goal': GoalService(db_session, redis_service),
        'deal': DealService(db_session, redis_service),
        'token': TokenService(db_session, redis_service)
    }

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
@depends_on("services.test_deal_service.test_create_deal")
@depends_on("services.test_token_service.test_service_fee")
async def test_goal_creation_workflow(db_session, services):
    """Test complete goal creation workflow with token deduction."""
    # Create user with initial balance
    user = await UserFactory.create_async(db_session=db_session)
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=Decimal("100.0")
    )
    
    # Create goal with token deduction
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
        "deadline": datetime.utcnow() + timedelta(days=30),
        "priority": 1,
        "max_matches": 10,
        "max_tokens": Decimal("50.0"),
        "notification_threshold": Decimal("0.8"),
        "auto_buy_threshold": Decimal("0.9")
    }
    
    goal = await services['goal'].create_goal(
        user_id=user.id,
        deduct_tokens=True,
        **goal_data
    )
    
    # Verify goal creation
    assert goal.title == goal_data["title"]
    assert goal.status == GoalStatus.ACTIVE.value
    
    # Verify token deduction
    balance = await services['token'].get_balance(user.id)
    assert balance < Decimal("100.0")

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
@depends_on("services.test_deal_service.test_create_deal")
async def test_goal_matching_workflow(db_session, services):
    """Test goal matching with deals workflow."""
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
            "keywords": ["laptop"],
            "categories": ["electronics"]
        }
    )
    
    # Create matching deal
    matching_deal = await DealFactory.create_async(
        db_session=db_session,
        title="Gaming Laptop",
        price=Decimal("999.99"),
        category="electronics"
    )
    
    # Create non-matching deal
    non_matching_deal = await DealFactory.create_async(
        db_session=db_session,
        title="Smartphone",
        price=Decimal("499.99"),
        category="electronics"
    )
    
    # Match deals with goal
    matches = await services['goal'].match_deals(goal.id)
    
    assert len(matches) == 1
    assert matches[0].id == matching_deal.id

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
async def test_goal_notification_workflow(db_session, services):
    """Test goal notification workflow."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create goal with notification settings
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user=user,
        notification_threshold=Decimal("0.8"),
        auto_buy_threshold=Decimal("0.9")
    )
    
    # Create deal that matches notification threshold
    deal = await DealFactory.create_async(
        db_session=db_session,
        original_price=Decimal("100.0"),
        price=Decimal("15.0")  # 85% discount
    )
    
    # Check notification trigger
    should_notify = await services['goal'].should_notify_user(
        goal_id=goal.id,
        deal_id=deal.id
    )
    assert should_notify
    
    # Check auto-buy trigger
    should_auto_buy = await services['goal'].should_auto_buy(
        goal_id=goal.id,
        deal_id=deal.id
    )
    assert not should_auto_buy  # 85% < 90% auto-buy threshold

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
async def test_goal_completion_workflow(db_session, services):
    """Test goal completion workflow."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create goal with max matches
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user=user,
        max_matches=2
    )
    
    # Create and match deals
    for i in range(3):
        deal = await DealFactory.create_async(
            db_session=db_session,
            goal=goal
        )
        await services['goal'].process_deal_match(
            goal_id=goal.id,
            deal_id=deal.id
        )
    
    # Verify goal status
    updated_goal = await services['goal'].get_goal(goal.id)
    assert updated_goal.status == GoalStatus.COMPLETED.value

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
@depends_on("services.test_token_service.test_service_fee")
async def test_goal_token_limit_workflow(db_session, services):
    """Test goal token limit workflow."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create goal with token limit
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user=user,
        max_tokens=Decimal("10.0")
    )
    
    # Simulate token usage
    for i in range(5):
        await services['token'].deduct_service_fee(
            user_id=user.id,
            amount=Decimal("2.0"),
            service_type="goal_search"
        )
    
    # Verify goal is paused due to token limit
    updated_goal = await services['goal'].get_goal(goal.id)
    assert updated_goal.status == GoalStatus.PAUSED.value

@feature_test
@depends_on("services.test_goal_service.test_create_goal")
async def test_goal_deadline_workflow(db_session, services):
    """Test goal deadline workflow."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create goal with past deadline
    goal = await GoalFactory.create_async(
        db_session=db_session,
        user=user,
        deadline=datetime.utcnow() - timedelta(days=1)
    )
    
    # Check and update expired goals
    await services['goal'].check_expired_goals()
    
    # Verify goal status
    updated_goal = await services['goal'].get_goal(goal.id)
    assert updated_goal.status == GoalStatus.EXPIRED.value 