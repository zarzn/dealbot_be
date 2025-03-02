"""Test module for TokenBalance model.

This module contains tests for the TokenBalance model, which tracks user token balances
in the AI Agentic Deals System.
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from core.models.token_balance import TokenBalance, TokenBalanceCreate, TokenBalanceResponse
from core.models.token_balance_history import TokenBalanceHistory
from core.models.user import User
from core.models.enums import TransactionType
from core.exceptions import InsufficientBalanceError


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_balance_creation(async_session):
    """Test creating a token balance in the database."""
    # Create a test user first
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100.12345678"))
    async_session.add(token_balance)
    await async_session.commit()
    
    # Retrieve the token balance
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await async_session.execute(query)
    fetched_balance = result.scalar_one()
    
    # Assertions
    assert fetched_balance is not None
    assert fetched_balance.id is not None
    assert fetched_balance.user_id == user_id
    assert fetched_balance.balance == Decimal("100.12345678")
    assert fetched_balance.quantized_balance == Decimal("100.12345678")
    assert isinstance(fetched_balance.created_at, datetime)
    assert isinstance(fetched_balance.updated_at, datetime)
    
    # Test the unique constraint on user_id
    duplicate_balance = TokenBalance(user_id=user_id, balance=Decimal("200"))
    async_session.add(duplicate_balance)
    with pytest.raises(Exception):  # SQLAlchemy will raise an exception for unique constraint violation
        await async_session.commit()
    await async_session.rollback()


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_balance_relationships(async_session):
    """Test the relationships between token balance and user."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    async_session.add(token_balance)
    await async_session.commit()
    
    # Test user relationship
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await async_session.execute(query)
    fetched_balance = result.scalar_one()
    
    assert fetched_balance.user is not None
    assert fetched_balance.user.id == user_id
    assert fetched_balance.user.email == "test@example.com"
    
    # Test user -> token_balances relationship
    query = select(User).where(User.id == user_id)
    result = await async_session.execute(query)
    fetched_user = result.scalar_one()
    
    assert len(fetched_user.token_balances) == 1
    assert fetched_user.token_balances[0].id == token_balance.id
    assert fetched_user.token_balances[0].balance == Decimal("100")


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_balance_update(async_session):
    """Test updating token balance."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    async_session.add(token_balance)
    await async_session.commit()
    
    # Update balance using update_balance method - add funds
    updated_balance = await token_balance.update_balance(
        async_session,
        amount=Decimal("50"),
        operation=TransactionType.REWARD.value,
        reason="Test reward",
    )
    
    assert updated_balance.balance == Decimal("150.00000000")
    
    # Check that history record was created
    query = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await async_session.execute(query)
    history_records = result.scalars().all()
    
    assert len(history_records) == 1
    assert history_records[0].balance_before == Decimal("100.00000000")
    assert history_records[0].balance_after == Decimal("150.00000000")
    assert history_records[0].change_amount == Decimal("50.00000000")
    assert history_records[0].change_type == TransactionType.REWARD.value
    assert history_records[0].reason == "Test reward"
    
    # Deduct funds
    updated_balance = await token_balance.update_balance(
        async_session,
        amount=Decimal("30"),
        operation=TransactionType.DEDUCTION.value,
        reason="Test deduction",
    )
    
    assert updated_balance.balance == Decimal("120.00000000")
    
    # Check history records again
    query = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await async_session.execute(query)
    history_records = result.scalars().all()
    
    assert len(history_records) == 2
    assert history_records[1].balance_before == Decimal("150.00000000")
    assert history_records[1].balance_after == Decimal("120.00000000")
    assert history_records[1].change_amount == Decimal("30.00000000")
    assert history_records[1].change_type == TransactionType.DEDUCTION.value


@pytest.mark.asyncio
@pytest.mark.core
async def test_insufficient_balance_error(async_session):
    """Test that InsufficientBalanceError is raised when trying to deduct more than available."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create token balance with 100 tokens
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    async_session.add(token_balance)
    await async_session.commit()
    
    # Try to deduct more than available
    with pytest.raises(InsufficientBalanceError) as excinfo:
        await token_balance.update_balance(
            async_session,
            amount=Decimal("150"),
            operation=TransactionType.DEDUCTION.value,
            reason="Test failing deduction",
        )
    
    assert "Insufficient balance" in str(excinfo.value)
    
    # Verify balance remained unchanged
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await async_session.execute(query)
    fetched_balance = result.scalar_one()
    
    assert fetched_balance.balance == Decimal("100.00000000")


@pytest.mark.asyncio
@pytest.mark.core
async def test_balance_history_cascade(async_session):
    """Test that history records remain when updating the balance multiple times."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    async_session.add(token_balance)
    await async_session.commit()
    
    # Multiple balance updates
    operations = [
        {"amount": Decimal("50"), "operation": TransactionType.REWARD.value, "reason": "Reward 1"},
        {"amount": Decimal("25"), "operation": TransactionType.DEDUCTION.value, "reason": "Deduction 1"},
        {"amount": Decimal("10"), "operation": TransactionType.REFUND.value, "reason": "Refund 1"},
        {"amount": Decimal("15"), "operation": TransactionType.DEDUCTION.value, "reason": "Deduction 2"},
    ]
    
    expected_balance = Decimal("100")
    
    for op in operations:
        if op["operation"] in [TransactionType.REWARD.value, TransactionType.REFUND.value]:
            expected_balance += op["amount"]
        else:
            expected_balance -= op["amount"]
            
        await token_balance.update_balance(
            async_session,
            amount=op["amount"],
            operation=op["operation"],
            reason=op["reason"],
        )
    
    # Verify final balance
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await async_session.execute(query)
    fetched_balance = result.scalar_one()
    
    assert fetched_balance.balance == expected_balance.quantize(Decimal('0.00000000'))
    
    # Verify history records
    query = select(TokenBalanceHistory).where(
        TokenBalanceHistory.token_balance_id == token_balance.id
    ).order_by(TokenBalanceHistory.created_at)
    result = await async_session.execute(query)
    history_records = result.scalars().all()
    
    assert len(history_records) == len(operations)
    
    # Check each history record
    for i, record in enumerate(history_records):
        assert record.change_type == operations[i]["operation"]
        assert record.change_amount == operations[i]["amount"].quantize(Decimal('0.00000000'))
        assert record.reason == operations[i]["reason"]


@pytest.mark.asyncio
@pytest.mark.core
async def test_pydantic_models(async_session):
    """Test the Pydantic models associated with TokenBalance."""
    # Create TokenBalanceCreate instance
    user_id = uuid4()
    balance_create = TokenBalanceCreate(user_id=user_id, balance=Decimal("123.45678901"))
    
    # Verify validation
    assert balance_create.user_id == user_id
    assert balance_create.balance == Decimal("123.45678901")
    
    # Create a TokenBalance in the database
    token_balance = TokenBalance(
        user_id=user_id, 
        balance=balance_create.balance
    )
    async_session.add(token_balance)
    await async_session.commit()
    
    # Create TokenBalanceResponse from the model
    response = TokenBalanceResponse.model_validate(token_balance)
    
    assert response.id == token_balance.id
    assert response.user_id == user_id
    assert response.balance == Decimal("123.45678901")
    assert isinstance(response.created_at, datetime)
    assert isinstance(response.updated_at, datetime)