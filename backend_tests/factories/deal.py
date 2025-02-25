from decimal import Decimal
from factory import Faker, SubFactory, LazyAttribute
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from .base import BaseFactory
from core.models.deal import Deal
from core.models.enums import DealStatus, DealSource, MarketCategory
from .user import UserFactory
from .goal import GoalFactory
from .market import MarketFactory

class DealFactory(BaseFactory):
    class Meta:
        model = Deal

    title = Faker('sentence')
    description = Faker('text')
    url = Faker('url')
    price = Decimal("99.99")
    original_price = Decimal("149.99")
    currency = "USD"
    source = DealSource.MANUAL.value
    image_url = Faker('image_url')
    category = MarketCategory.ELECTRONICS.value
    status = DealStatus.ACTIVE.value
    seller_info = {
        "name": "Test Seller",
        "rating": 4.5,
        "reviews": 100
    }
    found_at = LazyAttribute(lambda _: datetime.utcnow())
    expires_at = LazyAttribute(lambda _: datetime.utcnow() + timedelta(days=30))
    
    # Define relationships
    user = SubFactory(UserFactory)
    goal = SubFactory(GoalFactory)
    market = SubFactory(MarketFactory)
    
    # Define foreign keys as lazy attributes from their related objects
    user_id = LazyAttribute(lambda o: o.user.id if o.user else uuid4())
    goal_id = LazyAttribute(lambda o: o.goal.id if o.goal else uuid4())
    market_id = LazyAttribute(lambda o: o.market.id if o.market else uuid4())

    @classmethod
    async def create_async(cls, db_session=None, **kwargs):
        """Create a Deal instance asynchronously.
        
        This method handles creation of related objects and ensures
        that required foreign keys are properly set.
        
        Args:
            db_session: Database session for creating the object
            **kwargs: Object attributes to set
            
        Returns:
            Deal instance
        """
        if db_session is None:
            raise ValueError("db_session is required for create_async")
            
        # Create dependencies if not provided
        if 'user' not in kwargs and 'user_id' not in kwargs:
            user = await UserFactory.create_async(db_session=db_session)
            kwargs['user'] = user
            kwargs['user_id'] = user.id
        elif 'user' in kwargs and kwargs['user'] is not None and 'user_id' not in kwargs:
            kwargs['user_id'] = kwargs['user'].id
            
        if 'market' not in kwargs and 'market_id' not in kwargs:
            market = await MarketFactory.create_async(db_session=db_session)
            kwargs['market'] = market
            kwargs['market_id'] = market.id
        elif 'market' in kwargs and kwargs['market'] is not None and 'market_id' not in kwargs:
            kwargs['market_id'] = kwargs['market'].id
            
        if 'goal' not in kwargs and 'goal_id' not in kwargs:
            goal = await GoalFactory.create_async(db_session=db_session)
            kwargs['goal'] = goal
            kwargs['goal_id'] = goal.id
        elif 'goal' in kwargs and kwargs['goal'] is not None and 'goal_id' not in kwargs:
            kwargs['goal_id'] = kwargs['goal'].id
            
        # Validate price
        price = kwargs.get('price', cls.price)
        if price <= 0:
            raise ValueError("Deal price must be positive")

        # Validate original price
        original_price = kwargs.get('original_price', cls.original_price)
        if original_price and original_price <= price:
            raise ValueError("Original price must be greater than current price")

        # Validate status
        status = kwargs.get('status', cls.status)
        if status not in [s.value for s in DealStatus]:
            raise ValueError(f"Invalid deal status: {status}")

        # Create deal
        return await super().create_async(db_session=db_session, **kwargs)
