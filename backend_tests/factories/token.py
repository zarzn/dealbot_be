"""Token transaction factory module."""

from typing import Optional
from decimal import Decimal, ROUND_DOWN
from factory import Faker, SubFactory
from .base import BaseFactory
from core.models.token_transaction import TokenTransaction
from core.models.token_balance import TokenBalance
from core.models.enums import TokenTransactionType, TokenTransactionStatus
from backend_tests.factories.user import UserFactory
from sqlalchemy import select
from uuid import uuid4

class TokenTransactionFactory(BaseFactory):
    class Meta:
        model = TokenTransaction
    
    user = SubFactory(UserFactory)
    amount = Decimal("10.0")  # Default amount
    type = TokenTransactionType.REWARD.value
    status = TokenTransactionStatus.COMPLETED.value  # Explicitly set default status
    tx_hash = Faker('uuid4')  # Generate a random transaction hash

    @classmethod
    async def create_async(cls, db_session=None, **kwargs):
        """Create a token transaction with proper precision handling."""
        if db_session is None:
            raise ValueError("db_session is required for create_async")

        # Create user if not provided
        if 'user' not in kwargs and 'user_id' not in kwargs:
            user = await UserFactory.create_async(db_session=db_session)
            kwargs['user'] = user
            
        # Ensure status is set
        if 'status' not in kwargs:
            kwargs['status'] = TokenTransactionStatus.COMPLETED.value

        # Create instance
        instance = cls.build(**kwargs)

        # Ensure user_id is set
        if not instance.user_id and instance.user:
            instance.user_id = instance.user.id
            
        # Make sure status is set
        if not instance.status:
            instance.status = TokenTransactionStatus.COMPLETED.value

        # Validate and quantize amount
        instance.validate_amount()
        instance.validate_type()
        instance.validate_status()

        # Add to session
        db_session.add(instance)

        # Process transaction if completed
        if instance.status == TokenTransactionStatus.COMPLETED.value:
            await instance.process(db_session)

        # Commit and refresh
        await db_session.commit()
        await db_session.refresh(instance)

        return instance

class TokenBalanceFactory(BaseFactory):
    """Factory for creating TokenBalance instances."""
    
    class Meta:
        model = TokenBalance
    
    user = SubFactory(UserFactory)
    balance = Decimal("100.00000000")  # Default balance
    
    @classmethod
    async def create_async(cls, db_session=None, **kwargs):
        """Create a token balance."""
        if db_session is None:
            raise ValueError("db_session is required for create_async")
            
        # Create user if not provided
        if 'user' not in kwargs and 'user_id' not in kwargs:
            user = await UserFactory.create_async(db_session=db_session)
            kwargs['user'] = user
            
        # Create instance
        instance = cls.build(**kwargs)
        
        # Ensure user_id is set
        if not instance.user_id and instance.user:
            instance.user_id = instance.user.id
            
        # Check if a balance already exists for this user
        result = await db_session.execute(
            select(TokenBalance).where(TokenBalance.user_id == instance.user_id)
        )
        existing_balance = result.scalar_one_or_none()
        
        if existing_balance:
            # Update existing balance
            existing_balance.balance = instance.balance
            instance = existing_balance
        else:
            # Add new balance
            db_session.add(instance)
            
        # Commit and refresh
        await db_session.commit()
        await db_session.refresh(instance)
        
        return instance
