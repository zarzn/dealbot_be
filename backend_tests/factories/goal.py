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
    deadline = LazyAttribute(lambda _: datetime.now(timezone.utc) + timedelta(days=30))
    max_matches = 10
    max_tokens = 1000.0
    notification_threshold = 0.8
    auto_buy_threshold = 0.9

    @post_generation
    def initialize_constraints(self, create: bool, extracted: dict, **kwargs):
        """Initialize constraints to ensure all required fields are present."""
        # Ensure constraints is a dictionary, not None
        if not hasattr(self, 'constraints') or not self.constraints:
            self.constraints = {}
        
        # Required fields with default values if missing
        required_fields = {
            'min_price': 100.0,
            'max_price': 500.0,
            'brands': ['samsung', 'apple', 'sony'],
            'conditions': ['new', 'like_new', 'good'],
            'keywords': ['electronics', 'gadget', 'tech']
        }
        
        # Add any missing required fields
        for field, default_value in required_fields.items():
            if field not in self.constraints:
                self.constraints[field] = default_value
        
        # Handle price_range if present
        if 'price_range' in self.constraints:
            price_range = self.constraints['price_range']
            if isinstance(price_range, dict):
                if 'min' in price_range:
                    self.constraints['min_price'] = float(price_range['min'])
                if 'max' in price_range:
                    self.constraints['max_price'] = float(price_range['max'])
            elif isinstance(price_range, list) and len(price_range) >= 2:
                # Handle [min, max] format
                self.constraints['min_price'] = float(price_range[0])
                self.constraints['max_price'] = float(price_range[1])

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
        
        # Initialize constraints if not present
        if 'constraints' not in kwargs:
            kwargs['constraints'] = {}
        elif kwargs['constraints'] is None:
            kwargs['constraints'] = {}
            
        # Handle description field - move it to constraints if present
        if 'description' in kwargs:
            description = kwargs.pop('description')
            # Add description to constraints without overriding existing constraints
            if 'constraints' not in kwargs:
                kwargs['constraints'] = {'description': description}
            else:
                kwargs['constraints']['description'] = description
            
        # Make sure all required constraint fields are present
        required_fields = {
            'min_price': 100.0,
            'max_price': 500.0,
            'brands': ['samsung', 'apple', 'sony'],
            'conditions': ['new', 'like_new', 'good'],
            'keywords': ['electronics', 'gadget', 'tech']
        }
        
        # Add any missing required fields to constraints
        for field, default_value in required_fields.items():
            if 'constraints' not in kwargs:
                kwargs['constraints'] = {}
            if field not in kwargs['constraints']:
                kwargs['constraints'][field] = default_value
        
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
        
        # Ensure deadline is timezone-aware if provided
        if 'deadline' in kwargs and kwargs['deadline'] is not None:
            if not kwargs['deadline'].tzinfo:
                kwargs['deadline'] = kwargs['deadline'].replace(tzinfo=timezone.utc)
                
            # Ensure deadline is in the future
            if kwargs['deadline'] <= datetime.now(timezone.utc):
                kwargs['deadline'] = datetime.now(timezone.utc) + timedelta(days=30)
        
        return await super().create_async(db_session=db_session, **kwargs)
