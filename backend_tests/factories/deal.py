from decimal import Decimal
from factory import Faker, SubFactory, LazyAttribute, Sequence
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
    # Use a sequence to ensure unique URLs
    url = Sequence(lambda n: f"https://example.com/deal/{n}")
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
        # Convert string price to Decimal if needed
        if isinstance(price, str):
            price = Decimal(price)
        if price <= 0:
            raise ValueError("Deal price must be positive")

        # Update kwargs with the converted price
        if 'price' in kwargs and isinstance(kwargs['price'], str):
            kwargs['price'] = price

        # Validate original price
        if 'price' in kwargs:
            # If price is specified, ensure original_price is higher than price
            if 'original_price' not in kwargs:
                # Make sure the difference between original_price and price is at least 0.01
                calculated_price = price * Decimal('1.5')  # 50% higher than the current price
                if calculated_price - price < Decimal('0.01'):
                    kwargs['original_price'] = price + Decimal('0.01')  # Ensure difference is at least 0.01
                else:
                    kwargs['original_price'] = calculated_price
            elif kwargs['original_price'] <= price:
                # If original_price is provided but not greater than price, adjust it
                kwargs['original_price'] = price + Decimal('0.01')  # Ensure difference is at least 0.01
        
        # Double check that original_price is greater than price
        original_price = kwargs.get('original_price', cls.original_price)
        price = kwargs.get('price', cls.price)
        if original_price and original_price <= price:
            kwargs['original_price'] = price + Decimal('0.01')  # Final safety check ensuring 0.01 difference

        # Ensure category is always set to a valid value (not None)
        if 'category' not in kwargs or kwargs['category'] is None:
            kwargs['category'] = MarketCategory.ELECTRONICS.value

        # Validate status
        status = kwargs.get('status', cls.status)
        if status not in [s.value for s in DealStatus]:
            raise ValueError(f"Invalid deal status: {status}")

        # Create deal
        return await super().create_async(db_session=db_session, **kwargs)
