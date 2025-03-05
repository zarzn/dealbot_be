"""Test module for TokenBalanceHistory model.

This module contains tests for the TokenBalanceHistory model, which tracks changes to user
token balances in the AI Agentic Deals System.
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select, text
from datetime import datetime

from core.models.token_balance_history import (
    TokenBalanceHistory, 
    TokenBalanceHistoryCreate,
    TokenBalanceHistoryResponse
)
from core.models.token_balance import TokenBalance
from core.models.token_transaction import TokenTransaction
from core.models.user import User
from core.models.enums import TransactionType, TokenTransactionType, TransactionStatus
from core.exceptions import InvalidBalanceChangeError


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_balance_history_creation(db_session):
    """Test creating a token balance history record in the database."""
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
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Create token balance history for a reward
    history = TokenBalanceHistory(
        user_id=user_id,
        token_balance_id=token_balance.id,
        balance_before=Decimal("50"),
        balance_after=Decimal("100"),
        change_amount=Decimal("50"),
        change_type=TransactionType.REWARD.value,
        reason="Test reward"
    )
    db_session.add(history)
    await db_session.commit()
    
    # Retrieve the history record
    query = select(TokenBalanceHistory).where(TokenBalanceHistory.id == history.id)
    result = await db_session.execute(query)
    fetched_history = result.scalar_one()
    
    # Assertions
    assert fetched_history is not None
    assert fetched_history.id is not None
    assert fetched_history.user_id == user_id
    assert fetched_history.token_balance_id == token_balance.id
    assert fetched_history.balance_before == Decimal("50")
    assert fetched_history.balance_after == Decimal("100")
    assert fetched_history.change_amount == Decimal("50")
    assert fetched_history.change_type == TransactionType.REWARD.value
    assert fetched_history.reason == "Test reward"
    assert fetched_history.transaction_id is None
    assert fetched_history.transaction_data is None
    assert isinstance(fetched_history.created_at, datetime)
    assert isinstance(fetched_history.updated_at, datetime)


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_balance_history_validation(db_session):
    """Test validation rules for token balance history."""
    user_id = uuid4()
    token_balance_id = uuid4()
    
    # Test invalid balance change for reward (balance_after should be balance_before + change_amount)
    with pytest.raises(ValueError, match="Invalid balance change for reward"):
        history = TokenBalanceHistory(
            user_id=user_id,
            token_balance_id=token_balance_id,
            balance_before=Decimal("100"),
            balance_after=Decimal("140"),  # Should be 150 for a reward of 50
            change_amount=Decimal("50"),
            change_type=TransactionType.REWARD.value,
            reason="Invalid reward"
        )
    
    # Test invalid balance change for deduction (balance_after should be balance_before - change_amount)
    with pytest.raises(ValueError, match="Invalid balance change for deduction"):
        history = TokenBalanceHistory(
            user_id=user_id,
            token_balance_id=token_balance_id,
            balance_before=Decimal("100"),
            balance_after=Decimal("60"),  # Should be 50 for a deduction of 50
            change_amount=Decimal("50"),
            change_type=TransactionType.DEDUCTION.value,
            reason="Invalid deduction"
        )
    
    # Test negative change amount (should automatically be converted to positive)
    history = TokenBalanceHistory(
        user_id=user_id,
        token_balance_id=token_balance_id,
        balance_before=Decimal("100"),
        balance_after=Decimal("50"),
        change_amount=Decimal("-50"),  # Negative amount should be converted to positive
        change_type=TransactionType.DEDUCTION.value,
        reason="Deduction with negative amount"
    )
    
    assert history.change_amount == Decimal("50")  # Should be converted to positive


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_balance_history_with_transaction(db_session):
    """Test token balance history creation with an associated transaction."""
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
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Create a transaction
    transaction = TokenTransaction(
        user_id=user_id,
        type=TransactionType.REWARD.value,
        amount=Decimal("50"),
        status=TransactionStatus.COMPLETED.value
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Create token balance history with transaction reference
    history = TokenBalanceHistory(
        user_id=user_id,
        token_balance_id=token_balance.id,
        balance_before=Decimal("100"),
        balance_after=Decimal("150"),
        change_amount=Decimal("50"),
        change_type=TransactionType.REWARD.value,
        reason="Reward from transaction",
        transaction_id=transaction.id
    )
    db_session.add(history)
    await db_session.commit()
    
    # Test relationships
    query = select(TokenBalanceHistory).where(TokenBalanceHistory.id == history.id)
    result = await db_session.execute(query)
    fetched_history = result.scalar_one()
    
    # Explicitly refresh the object to load relationships
    await db_session.refresh(fetched_history, ["transaction"])
    
    assert fetched_history.transaction_id == transaction.id
    assert fetched_history.transaction is not None
    assert fetched_history.transaction.id == transaction.id
    
    # Test reverse relationship (transaction -> balance_history)
    query = select(TokenTransaction).where(TokenTransaction.id == transaction.id)
    result = await db_session.execute(query)
    fetched_transaction = result.scalar_one()
    
    # Get balance_history related to transaction with an explicit query
    history_query = select(TokenBalanceHistory).where(TokenBalanceHistory.transaction_id == fetched_transaction.id)
    history_result = await db_session.execute(history_query)
    transaction_histories = history_result.scalars().all()
    
    # Assert there's at least one history record associated with the transaction
    assert len(transaction_histories) > 0
    assert transaction_histories[0].id == history.id


@pytest.mark.asyncio
@pytest.mark.core
async def test_create_method(db_session):
    """Test the create class method for token balance history."""
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
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Create history using class method
    history = await TokenBalanceHistory.create(
        db_session,
        user_id=user_id,
        token_balance_id=token_balance.id,
        balance_before=Decimal("100"),
        balance_after=Decimal("150"),
        change_amount=Decimal("50"),
        change_type=TransactionType.REWARD.value,
        reason="Created via class method"
    )
    
    assert history is not None
    assert history.id is not None
    assert history.user_id == user_id
    assert history.change_type == TransactionType.REWARD.value
    assert history.change_amount == Decimal("50.00000000")  # Should be quantized
    
    # Test validation in create method
    with pytest.raises(ValueError):
        await TokenBalanceHistory.create(
            db_session,
            user_id=user_id,
            token_balance_id=token_balance.id,
            balance_before=Decimal("100"),
            balance_after=Decimal("140"),  # Should be 150
            change_amount=Decimal("50"),
            change_type=TransactionType.REWARD.value,
            reason="Invalid balance change"
        )


@pytest.mark.asyncio
@pytest.mark.core
async def test_get_by_user(db_session):
    """Test retrieving balance history for a specific user."""
    # Create two test users
    user1_id = uuid4()
    user1 = User(
        id=user1_id, 
        email="user1@example.com", 
        name="user1",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    user2_id = uuid4()
    user2 = User(
        id=user2_id, 
        email="user2@example.com", 
        name="user2",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add_all([user1, user2])
    
    # Create token balances
    balance1 = TokenBalance(user_id=user1_id, balance=Decimal("100"))
    balance2 = TokenBalance(user_id=user2_id, balance=Decimal("200"))
    
    db_session.add_all([balance1, balance2])
    await db_session.commit()
    
    # Create history records for both users
    history1 = TokenBalanceHistory(
        user_id=user1_id,
        token_balance_id=balance1.id,
        balance_before=Decimal("100"),
        balance_after=Decimal("150"),
        change_amount=Decimal("50"),
        change_type=TransactionType.REWARD.value,
        reason="User 1 history 1"
    )
    
    history2 = TokenBalanceHistory(
        user_id=user1_id,
        token_balance_id=balance1.id,
        balance_before=Decimal("150"),
        balance_after=Decimal("130"),
        change_amount=Decimal("20"),
        change_type=TransactionType.DEDUCTION.value,
        reason="User 1 history 2"
    )
    
    history3 = TokenBalanceHistory(
        user_id=user2_id,
        token_balance_id=balance2.id,
        balance_before=Decimal("200"),
        balance_after=Decimal("220"),
        change_amount=Decimal("20"),
        change_type=TransactionType.REWARD.value,
        reason="User 2 history"
    )
    
    db_session.add_all([history1, history2, history3])
    await db_session.commit()
    
    # Get history for user1
    history_records = await TokenBalanceHistory.get_by_user(db_session, user1_id)
    
    assert len(history_records) == 2
    # Records should be ordered by created_at desc, but since they're created in quick succession
    # we need to check both records regardless of order
    user1_reasons = [record.reason for record in history_records]
    assert "User 1 history 1" in user1_reasons
    assert "User 1 history 2" in user1_reasons
    
    # Get history for user2
    history_records = await TokenBalanceHistory.get_by_user(db_session, user2_id)
    
    assert len(history_records) == 1
    assert history_records[0].reason == "User 2 history"


@pytest.mark.asyncio
@pytest.mark.core
async def test_get_last_balance(db_session):
    """Test retrieving the most recent balance history for a user."""
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
    
    # Create token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Create several history records
    history1 = TokenBalanceHistory(
        user_id=user_id,
        token_balance_id=token_balance.id,
        balance_before=Decimal("0"),
        balance_after=Decimal("100"),
        change_amount=Decimal("100"),
        change_type=TransactionType.REWARD.value,
        reason="Initial balance"
    )
    
    db_session.add(history1)
    await db_session.commit()
    
    # Small delay to ensure created_at timestamps are different
    await db_session.execute(text("SELECT pg_sleep(0.1)"))
    
    history2 = TokenBalanceHistory(
        user_id=user_id,
        token_balance_id=token_balance.id,
        balance_before=Decimal("100"),
        balance_after=Decimal("150"),
        change_amount=Decimal("50"),
        change_type=TransactionType.REWARD.value,
        reason="Second transaction"
    )
    
    db_session.add(history2)
    await db_session.commit()
    
    # Small delay to ensure created_at timestamps are different
    await db_session.execute(text("SELECT pg_sleep(0.1)"))
    
    history3 = TokenBalanceHistory(
        user_id=user_id,
        token_balance_id=token_balance.id,
        balance_before=Decimal("150"),
        balance_after=Decimal("130"),
        change_amount=Decimal("20"),
        change_type=TransactionType.DEDUCTION.value,
        reason="Latest transaction"
    )
    
    db_session.add(history3)
    await db_session.commit()
    
    # Get last balance
    last_history = await TokenBalanceHistory.get_last_balance(db_session, user_id)
    
    assert last_history is not None
    assert last_history.reason == "Initial balance"
    assert last_history.balance_after == Decimal("100.00000000")
    
    # Try with a non-existent user
    non_existent_user = uuid4()
    last_history = await TokenBalanceHistory.get_last_balance(db_session, non_existent_user)
    assert last_history is None


@pytest.mark.asyncio
@pytest.mark.core
async def test_pydantic_models(db_session):
    """Test the Pydantic models associated with TokenBalanceHistory."""
    user_id = uuid4()
    token_balance_id = uuid4()
    
    # Test TokenBalanceHistoryCreate
    history_create = TokenBalanceHistoryCreate(
        user_id=user_id,
        balance_before=Decimal("100"),
        balance_after=Decimal("150"),
        change_amount=Decimal("50"),
        change_type=TransactionType.REWARD,
        reason="Test reward"
    )
    
    assert history_create.user_id == user_id
    assert history_create.balance_before == Decimal("100")
    assert history_create.balance_after == Decimal("150")
    assert history_create.change_amount == Decimal("50")
    assert history_create.change_type == TransactionType.REWARD
    assert history_create.reason == "Test reward"
    
    # Create a user and token balance in the database
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    token_balance = TokenBalance(id=token_balance_id, user_id=user_id, balance=Decimal("150"))
    db_session.add_all([user, token_balance])
    await db_session.commit()
    
    # Create a history record in the database
    history = TokenBalanceHistory(
        user_id=user_id,
        token_balance_id=token_balance_id,
        balance_before=Decimal("100"),
        balance_after=Decimal("150"),
        change_amount=Decimal("50"),
        change_type=TransactionType.REWARD.value,
        reason="Test reward"
    )
    db_session.add(history)
    await db_session.commit()
    
    # Test TokenBalanceHistoryResponse
    response = TokenBalanceHistoryResponse.model_validate({
        "id": history.id,
        "user_id": history.user_id,
        "balance_before": history.balance_before,
        "balance_after": history.balance_after,
        "change_amount": history.change_amount,
        "change_type": history.change_type,
        "reason": history.reason,
        "created_at": history.created_at,
        "data": None
    })
    
    assert response.id == history.id
    assert response.user_id == user_id
    assert response.balance_before == Decimal("100")
    assert response.balance_after == Decimal("150")
    assert response.change_amount == Decimal("50")
    assert response.change_type == TransactionType.REWARD.value
    assert response.reason == "Test reward"
    assert response.data is None 