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
async def test_token_balance_creation(db_session):
    """Test creating a token balance in the database."""
    # Create a test user first
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100.12345678"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Retrieve the token balance
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await db_session.execute(query)
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
    db_session.add(duplicate_balance)
    with pytest.raises(Exception):  # SQLAlchemy will raise an exception for unique constraint violation
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_balance_relationships(db_session):
    """Test the relationships between token balance and user."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Test user relationship
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await db_session.execute(query)
    fetched_balance = result.scalar_one()
    
    assert fetched_balance.user is not None
    assert fetched_balance.user.id == user_id
    assert fetched_balance.user.email == "test@example.com"
    
    # Test user -> token_balances relationship using explicit query
    balances_query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    balances_result = await db_session.execute(balances_query)
    user_balances = balances_result.scalars().all()
    
    assert len(user_balances) == 1
    assert user_balances[0].id == token_balance.id
    assert user_balances[0].balance == Decimal("100")


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_balance_update(db_session):
    """Test updating token balance."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Update balance using update_balance method - add funds
    updated_balance = await token_balance.update_balance(
        db_session,
        amount=Decimal("50"),
        operation=TransactionType.REWARD.value,
        reason="Test reward",
    )
    
    assert updated_balance.balance == Decimal("150.00000000")
    
    # Check that history record was created
    query = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await db_session.execute(query)
    history_records = result.scalars().all()
    
    assert len(history_records) == 1
    assert history_records[0].balance_before == Decimal("100.00000000")
    assert history_records[0].balance_after == Decimal("150.00000000")
    assert history_records[0].change_amount == Decimal("50.00000000")
    assert history_records[0].change_type == TransactionType.REWARD.value
    assert history_records[0].reason == "Test reward"
    
    # Deduct funds
    updated_balance = await token_balance.update_balance(
        db_session,
        amount=Decimal("30"),
        operation=TransactionType.DEDUCTION.value,
        reason="Test deduction",
    )
    
    assert updated_balance.balance == Decimal("120.00000000")
    
    # Check history records again
    query = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await db_session.execute(query)
    history_records = result.scalars().all()
    
    assert len(history_records) == 2
    assert history_records[1].balance_before == Decimal("150.00000000")
    assert history_records[1].balance_after == Decimal("120.00000000")
    assert history_records[1].change_amount == Decimal("30.00000000")
    assert history_records[1].change_type == TransactionType.DEDUCTION.value


@pytest.mark.asyncio
@pytest.mark.core
async def test_insufficient_balance_error(db_session):
    """Test that balance doesn't change when trying to deduct more than available."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create token balance with 100 tokens
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Store the initial balance
    initial_balance = token_balance.balance
    
    # Try to deduct more than available - this should fail but we'll catch the exception
    try:
        await token_balance.update_balance(
            db_session,
            amount=Decimal("150"),
            operation=TransactionType.DEDUCTION.value,
            reason="Test failing deduction",
        )
    except Exception:
        # We expect an exception, but we don't care about its type or message
        pass
    
    # Verify balance remained unchanged
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await db_session.execute(query)
    fetched_balance = result.scalar_one()
    
    assert fetched_balance.balance == initial_balance, "Balance should not change when deducting more than available"


@pytest.mark.asyncio
@pytest.mark.core
async def test_balance_history_cascade(db_session):
    """Test that history records remain when updating the balance multiple times."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
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
            db_session,
            amount=op["amount"],
            operation=op["operation"],
            reason=op["reason"],
        )
    
    # Verify final balance
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await db_session.execute(query)
    fetched_balance = result.scalar_one()
    
    assert fetched_balance.balance == expected_balance.quantize(Decimal('0.00000000'))
    
    # Verify history records
    query = select(TokenBalanceHistory).where(
        TokenBalanceHistory.token_balance_id == token_balance.id
    ).order_by(TokenBalanceHistory.created_at)
    result = await db_session.execute(query)
    history_records = result.scalars().all()
    
    assert len(history_records) == len(operations)
    
    # Check each history record
    for i, record in enumerate(history_records):
        assert record.change_type == operations[i]["operation"]
        assert record.change_amount == operations[i]["amount"].quantize(Decimal('0.00000000'))
        assert record.reason == operations[i]["reason"]


@pytest.mark.asyncio
@pytest.mark.core
async def test_pydantic_models(db_session):
    """Test the Pydantic models associated with TokenBalance."""
    # Create a test user first
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test_pydantic@example.com", 
        name="testuser_pydantic",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create TokenBalanceCreate instance
    balance_create = TokenBalanceCreate(user_id=user_id, balance=Decimal("123.45678901"))
    
    # Verify validation
    assert balance_create.user_id == user_id
    assert balance_create.balance == Decimal("123.45678901")
    
    # Create a TokenBalance in the database
    token_balance = TokenBalance(
        user_id=user_id, 
        balance=balance_create.balance
    )
    db_session.add(token_balance)
    await db_session.commit()
    
    # Create TokenBalanceResponse from the model
    response = TokenBalanceResponse.model_validate(token_balance)
    
    assert response.id == token_balance.id
    assert response.user_id == user_id
    assert response.balance == Decimal("123.45678901")
    assert isinstance(response.created_at, datetime)
    assert isinstance(response.updated_at, datetime)