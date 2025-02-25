from typing import Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID
from factory import Faker, SubFactory, LazyAttribute, post_generation
from .base import BaseFactory
from core.models.goal import Goal
from core.models.enums import GoalStatus, GoalPriority
from core.models.market import MarketCategory
from .user import UserFactory

class GoalFactory(BaseFactory):
    class Meta:
        model = Goal

    id = Faker('uuid4')
    user = SubFactory(UserFactory)
    user_id = LazyAttribute(lambda o: o.user.id if o.user else None)
    title = Faker('sentence', nb_words=4)
    item_category = MarketCategory.ELECTRONICS.value
    constraints = {
        'min_price': 100.0,
        'max_price': 500.0,
        'brands': ['samsung', 'apple', 'sony'],
        'conditions': ['new', 'like_new', 'good'],
        'keywords': ['electronics', 'gadget', 'tech']
    }
    status = GoalStatus.ACTIVE.value
    priority = GoalPriority.MEDIUM.value
    created_at = LazyAttribute(lambda _: datetime.now(timezone.utc))
    updated_at = LazyAttribute(lambda _: datetime.now(timezone.utc))
    deadline = LazyAttribute(lambda _: datetime.now(timezone.utc).replace(year=datetime.now().year + 1))
    max_matches = 10
    max_tokens = 1000.0
    notification_threshold = 0.8
    auto_buy_threshold = 0.9

    @post_generation
    def initialize_constraints(self, create: bool, extracted: dict, **kwargs):
        """Initialize constraints if not already set."""
        if not hasattr(self, 'constraints') or not self.constraints:
            self.constraints = {
                'min_price': float(100.0),
                'max_price': float(500.0),
                'brands': ['samsung', 'apple', 'sony'],
                'conditions': ['new', 'like_new', 'good'],
                'keywords': ['electronics', 'gadget', 'tech']
            }
        
        # Ensure constraints is a dictionary, not a string
        if isinstance(self.constraints, str):
            try:
                self.constraints = eval(self.constraints)
            except:
                self.constraints = {
                    'min_price': float(100.0),
                    'max_price': float(500.0),
                    'brands': ['samsung', 'apple', 'sony'],
                    'conditions': ['new', 'like_new', 'good'],
                    'keywords': ['electronics', 'gadget', 'tech']
                }

    @classmethod
    async def create_async(cls, db_session=None, **kwargs):
        """Create a new instance with proper user_id handling.
        
        Args:
            db_session: Database session (required)
            **kwargs: Additional goal attributes including user or user_id
            
        Returns:
            Goal: The created goal instance
            
        Raises:
            ValueError: If db_session is not provided
        """
        if db_session is None:
            raise ValueError("db_session is required for create_async")
        
        # If neither user nor user_id is provided, create a new user
        if 'user' not in kwargs and 'user_id' not in kwargs:
            user = await UserFactory.create_async(db_session=db_session)
            kwargs['user'] = user
            kwargs['user_id'] = user.id
        
        # If user is provided but user_id is not, set user_id from user
        elif 'user' in kwargs and 'user_id' not in kwargs:
            if kwargs['user'] is None:
                # If user is explicitly set to None, create a new user
                user = await UserFactory.create_async(db_session=db_session)
                kwargs['user'] = user
                kwargs['user_id'] = user.id
            else:
                kwargs['user_id'] = kwargs['user'].id
        
        # If user_id is provided but user is not, we need to ensure user exists
        elif 'user_id' in kwargs and 'user' not in kwargs:
            from core.models.user import User
            from sqlalchemy import select
            
            # Check if the user exists
            query = select(User).where(User.id == kwargs['user_id'])
            result = await db_session.execute(query)
            user = result.scalars().first()
            
            if not user:
                # Create a user if it doesn't exist
                new_user = await UserFactory.create_async(db_session=db_session)
                kwargs['user_id'] = new_user.id
                kwargs['user'] = new_user
        
        return await super().create_async(db_session=db_session, **kwargs)
