"""Test module for TokenTransaction model.

This module contains tests for the TokenTransaction model, which tracks token transactions
in the AI Agentic Deals System.
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select
from datetime import datetime

from core.models.token_transaction import (
    TokenTransaction, 
    TokenTransactionCreate,
    TokenTransactionInDB, 
    TransactionResponse
)
from core.models.token_balance import TokenBalance
from core.models.token_balance_history import TokenBalanceHistory
from core.models.user import User
from core.models.enums import TokenTransactionType, TokenTransactionStatus


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_transaction_creation(db_session):
    """Test creating a token transaction in the database."""
    # Create a test user first
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", name="Test User", password="password", status="active")
    db_session.add(user)
    await db_session.commit()
    
    # Create token transaction
    transaction = TokenTransaction(
        user_id=user_id,
        type=TokenTransactionType.REWARD.value,
        amount=Decimal("50.12345678"),
        status=TokenTransactionStatus.PENDING.value
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Retrieve the transaction
    query = select(TokenTransaction).where(TokenTransaction.id == transaction.id)
    result = await db_session.execute(query)
    fetched_transaction = result.scalar_one()
    
    # Assertions
    assert fetched_transaction is not None
    assert fetched_transaction.id is not None
    assert fetched_transaction.user_id == user_id
    assert fetched_transaction.type == TokenTransactionType.REWARD.value
    assert fetched_transaction.amount == Decimal("50.12345678")
    assert fetched_transaction.status == TokenTransactionStatus.PENDING.value
    assert fetched_transaction.tx_hash is None
    assert fetched_transaction.block_number is None
    assert fetched_transaction.meta_data is None
    assert fetched_transaction.error is None
    assert fetched_transaction.retry_count == 0
    assert fetched_transaction.max_retries == 3
    assert isinstance(fetched_transaction.created_at, datetime)
    assert isinstance(fetched_transaction.updated_at, datetime)
    assert fetched_transaction.completed_at is None


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_transaction_relationships(db_session):
    """Test the relationships between token transactions, users, and balance history."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", name="Test User", password="password", status="active")
    db_session.add(user)
    
    # Create token balance for the user
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    
    # Create token transaction
    transaction = TokenTransaction(
        user_id=user_id,
        type=TokenTransactionType.REWARD.value,
        amount=Decimal("50"),
        status=TokenTransactionStatus.COMPLETED.value
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Test user relationship
    query = select(TokenTransaction).where(TokenTransaction.id == transaction.id)
    result = await db_session.execute(query)
    fetched_transaction = result.scalar_one()
    
    assert fetched_transaction.user is not None
    assert fetched_transaction.user.id == user_id
    assert fetched_transaction.user.email == "test@example.com"
    
    # Test user -> token_transactions relationship
    query = select(User).where(User.id == user_id)
    result = await db_session.execute(query)
    fetched_user = result.scalar_one()
    
    assert len(fetched_user.token_transactions) == 1
    assert fetched_user.token_transactions[0].id == transaction.id
    assert fetched_user.token_transactions[0].amount == Decimal("50")


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_transaction_process(db_session):
    """Test transaction processing and balance updates."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", name="Test User", password="password", status="active")
    db_session.add(user)
    
    # Create initial token balance
    token_balance = TokenBalance(user_id=user_id, balance=Decimal("100"))
    db_session.add(token_balance)
    await db_session.commit()
    
    # Create and process a reward transaction
    transaction = TokenTransaction(
        user_id=user_id,
        type=TokenTransactionType.REWARD.value,
        amount=Decimal("50"),
        status=TokenTransactionStatus.PENDING.value
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Update status to COMPLETED to trigger processing
    transaction.status = TokenTransactionStatus.COMPLETED.value
    await transaction.process(db_session)
    
    # Verify balance was updated
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await db_session.execute(query)
    updated_balance = result.scalar_one()
    
    assert updated_balance.balance == Decimal("150.00000000")
    
    # Verify balance history was created
    query = select(TokenBalanceHistory).where(TokenBalanceHistory.transaction_id == transaction.id)
    result = await db_session.execute(query)
    history_record = result.scalar_one()
    
    assert history_record.balance_before == Decimal("100.00000000")
    assert history_record.balance_after == Decimal("150.00000000")
    assert history_record.change_amount == Decimal("50.00000000")
    assert history_record.change_type == TokenTransactionType.REWARD.value
    
    # Create and process a deduction transaction
    deduction = TokenTransaction(
        user_id=user_id,
        type=TokenTransactionType.DEDUCTION.value,
        amount=Decimal("30"),
        status=TokenTransactionStatus.COMPLETED.value
    )
    db_session.add(deduction)
    await deduction.process(db_session)
    
    # Verify balance was updated
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await db_session.execute(query)
    updated_balance = result.scalar_one()
    
    assert updated_balance.balance == Decimal("120.00000000")


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_transaction_validation(db_session):
    """Test validation of transaction properties."""
    user_id = uuid4()
    
    # Test negative amount validation
    with pytest.raises(ValueError, match="Transaction amount must be positive"):
        transaction = TokenTransaction(
            user_id=user_id,
            type=TokenTransactionType.REWARD.value,
            amount=Decimal("-10"),
            status=TokenTransactionStatus.PENDING.value
        )
        transaction.validate_amount()
    
    # Test invalid type validation
    with pytest.raises(ValueError, match="Invalid transaction type"):
        transaction = TokenTransaction(
            user_id=user_id,
            type="invalid_type",
            amount=Decimal("10"),
            status=TokenTransactionStatus.PENDING.value
        )
        transaction.validate_type()
    
    # Test invalid status validation
    with pytest.raises(ValueError, match="Invalid transaction status"):
        transaction = TokenTransaction(
            user_id=user_id,
            type=TokenTransactionType.REWARD.value,
            amount=Decimal("10"),
            status="invalid_status"
        )
        transaction.validate_status()


@pytest.mark.asyncio
@pytest.mark.core
async def test_token_transaction_update_status(db_session):
    """Test updating a transaction's status."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", name="Test User", password="password", status="active")
    db_session.add(user)
    await db_session.commit()
    
    # Create token transaction
    transaction = TokenTransaction(
        user_id=user_id,
        type=TokenTransactionType.REWARD.value,
        amount=Decimal("50"),
        status=TokenTransactionStatus.PENDING.value
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Update status using class method
    tx_hash = "0x" + "a" * 64
    updated_transaction = await TokenTransaction.update_status(
        db_session,
        transaction.id,
        TokenTransactionStatus.COMPLETED,
        tx_hash=tx_hash
    )
    
    assert updated_transaction.status == TokenTransactionStatus.COMPLETED.value
    assert updated_transaction.tx_hash == tx_hash


@pytest.mark.asyncio
@pytest.mark.core
async def test_pydantic_models(db_session):
    """Test the Pydantic models associated with TokenTransaction."""
    user_id = uuid4()
    
    # Create a test user to avoid foreign key violation
    user = User(
        id=user_id, 
        email="test_tx@example.com", 
        name="Test TX User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Test TokenTransactionCreate
    tx_create = TokenTransactionCreate(
        user_id=user_id,
        type=TokenTransactionType.REWARD,
        amount=50.0,
        status=TokenTransactionStatus.PENDING
    )
    
    assert tx_create.user_id == user_id
    assert tx_create.type == TokenTransactionType.REWARD
    assert tx_create.amount == 50.0
    assert tx_create.status == TokenTransactionStatus.PENDING
    
    # Create a transaction in the database
    transaction = TokenTransaction(
        user_id=user_id,
        type=TokenTransactionType.REWARD.value,
        amount=Decimal("50"),
        status=TokenTransactionStatus.PENDING.value
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Test TokenTransactionInDB
    tx_in_db = TokenTransactionInDB.model_validate(transaction)
    
    assert tx_in_db.id == transaction.id
    assert tx_in_db.user_id == user_id
    assert tx_in_db.type == TokenTransactionType.REWARD
    assert tx_in_db.amount == 50.0
    assert tx_in_db.created_at == transaction.created_at


@pytest.mark.asyncio
@pytest.mark.core
async def test_transaction_automatic_balance_creation(db_session):
    """Test that a token balance is automatically created when processing a transaction for a user without one."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", name="Test User", password="password", status="active")
    db_session.add(user)
    await db_session.commit()
    
    # Create transaction without creating a balance first
    transaction = TokenTransaction(
        user_id=user_id,
        type=TokenTransactionType.REWARD.value,
        amount=Decimal("100"),
        status=TokenTransactionStatus.COMPLETED.value
    )
    db_session.add(transaction)
    
    # Process the transaction - this should create a balance
    await transaction.process(db_session)
    
    # Verify a balance was created
    query = select(TokenBalance).where(TokenBalance.user_id == user_id)
    result = await db_session.execute(query)
    balance = result.scalar_one()
    
    assert balance is not None
    assert balance.balance == Decimal("100.00000000")


@pytest.mark.asyncio
@pytest.mark.core
async def test_quantized_amount(db_session):
    """Test the quantized_amount property."""
    # Create a transaction
    transaction = TokenTransaction(
        user_id=uuid4(),
        type=TokenTransactionType.REWARD.value,
        amount=Decimal("123.456789123456"),  # More than 8 decimal places
        status=TokenTransactionStatus.PENDING.value
    )
    
    # Test getter - should truncate to 8 decimal places
    assert transaction.quantized_amount == Decimal("123.45678912")
    
    # Test setter - should set with 8 decimal places
    transaction.quantized_amount = Decimal("50.123456789")
    assert transaction.amount == Decimal("50.12345678") 