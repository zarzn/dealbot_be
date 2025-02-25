"""Token balance model tests."""

import asyncio
import pytest
import time_machine
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, text
from core.database import AsyncSessionLocal
from core.models.token_balance import TokenBalance, TokenBalanceHistory
from core.models.enums import TokenOperation, TransactionType
from core.exceptions import (
    InsufficientBalanceError,
    InvalidBalanceChangeError,
    TokenBalanceError,
    TokenOperationError
)
from core.models.user import User
from uuid import uuid4

@pytest.mark.asyncio
async def test_create_token_balance(async_session: AsyncSession, test_user: User):
    """Test creating a token balance."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    
    assert token_balance.id is not None
    assert token_balance.user_id == test_user.id
    assert token_balance.balance == Decimal("100.0")
    assert token_balance.created_at is not None
    assert token_balance.updated_at is not None

@pytest.mark.asyncio
@time_machine.travel("2025-02-21 09:00:00+00:00")
async def test_update_balance_deduction(async_session: AsyncSession, test_user: User):
    """Test deducting from token balance."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    
    # Get current timestamp before starting transaction
    before_update = datetime.now(timezone.utc)
    
    # Travel forward 1 second
    time_machine.travel(before_update + timedelta(seconds=1))

    async with async_session.begin_nested():
        await token_balance.update_balance(
            db=async_session,
            amount=Decimal("-50.0"),
            operation=TransactionType.DEDUCTION.value,
            reason="test deduction"
        )

    await async_session.refresh(token_balance)
    assert token_balance.balance == Decimal("50.0")
    assert token_balance.updated_at > before_update

    # Check history record
    stmt = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await async_session.execute(stmt)
    history = result.scalar_one()
    assert history.balance_before == Decimal("100.0")
    assert history.balance_after == Decimal("50.0")
    assert history.change_amount == Decimal("50.0")
    assert history.change_type == TransactionType.DEDUCTION.value
    assert history.reason == "test deduction"

@pytest.mark.asyncio
@time_machine.travel("2025-02-21 09:00:00+00:00")
async def test_update_balance_reward(async_session: AsyncSession, test_user: User):
    """Test adding reward to token balance."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    
    # Get current timestamp before starting transaction
    before_update = datetime.now(timezone.utc)
    
    # Travel forward 1 second
    time_machine.travel(before_update + timedelta(seconds=1))

    async with async_session.begin_nested():
        await token_balance.update_balance(
            db=async_session,
            amount=Decimal("50.0"),
            operation=TransactionType.REWARD.value,
            reason="test reward"
        )

    await async_session.refresh(token_balance)
    assert token_balance.balance == Decimal("150.0")
    assert token_balance.updated_at > before_update

    # Check history record
    stmt = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await async_session.execute(stmt)
    history = result.scalar_one()
    assert history.balance_before == Decimal("100.0")
    assert history.balance_after == Decimal("150.0")
    assert history.change_amount == Decimal("50.0")
    assert history.change_type == TransactionType.REWARD.value
    assert history.reason == "test reward"

@pytest.mark.asyncio
@time_machine.travel("2025-02-21 09:00:00+00:00")
async def test_insufficient_balance_error(async_session: AsyncSession, test_user: User):
    """Test insufficient balance error."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    initial_balance = token_balance.balance
    initial_updated_at = token_balance.updated_at

    with pytest.raises(InsufficientBalanceError) as exc_info:
        async with async_session.begin_nested():
            await token_balance.update_balance(
                db=async_session,
                amount=Decimal("150.0"),
                operation=TransactionType.DEDUCTION.value,
                reason="Test insufficient balance"
            )
    
    assert exc_info.value.required == Decimal("150.0")
    assert exc_info.value.available == initial_balance
    await async_session.refresh(token_balance)
    assert token_balance.balance == initial_balance
    assert token_balance.updated_at == initial_updated_at

    # Check no history record was created
    stmt = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await async_session.execute(stmt)
    assert result.first() is None

@pytest.mark.asyncio
@time_machine.travel("2025-02-21 09:00:00+00:00")
async def test_invalid_operation_error(async_session: AsyncSession, test_user: User):
    """Test invalid operation error."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    initial_balance = token_balance.balance
    initial_updated_at = token_balance.updated_at

    with pytest.raises(InvalidBalanceChangeError, match="Invalid operation type"):
        async with async_session.begin_nested():
            await token_balance.update_balance(
                db=async_session,
                amount=Decimal("50.0"),
                operation="invalid_operation",
                reason="Test invalid operation"
            )

    await async_session.refresh(token_balance)
    assert token_balance.balance == initial_balance
    assert token_balance.updated_at == initial_updated_at

    # Check no history record was created
    stmt = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await async_session.execute(stmt)
    assert result.first() is None

@pytest.mark.asyncio
@time_machine.travel("2025-02-21 09:00:00+00:00")
async def test_negative_balance_validation(async_session: AsyncSession, test_user: User):
    """Test that negative balance is not allowed."""
    with pytest.raises(InvalidBalanceChangeError, match="Balance cannot be negative"):
        async with async_session.begin_nested():
            token_balance = TokenBalance(
                user_id=test_user.id,
                balance=Decimal("-100.0")
            )
            async_session.add(token_balance)
            await async_session.flush()

@pytest.mark.asyncio
@time_machine.travel("2025-02-21 09:00:00+00:00")
async def test_refund_operation(async_session: AsyncSession, test_user: User):
    """Test refund operation."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    
    # Get current timestamp before starting transaction
    before_update = datetime.now(timezone.utc)
    
    # Travel forward 1 second
    time_machine.travel(before_update + timedelta(seconds=1))

    async with async_session.begin_nested():
        await token_balance.update_balance(
            db=async_session,
            amount=Decimal("25.0"),
            operation=TransactionType.REFUND.value,
            reason="test refund"
        )

    await async_session.refresh(token_balance)
    assert token_balance.balance == Decimal("125.0")
    assert token_balance.updated_at > before_update

    # Check history record
    stmt = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await async_session.execute(stmt)
    history = result.scalar_one()
    assert history.balance_before == Decimal("100.0")
    assert history.balance_after == Decimal("125.0")
    assert history.change_amount == Decimal("25.0")
    assert history.change_type == TransactionType.REFUND.value
    assert history.reason == "test refund"

@pytest.mark.asyncio
async def test_user_relationship(async_session: AsyncSession, test_user: User):
    """Test user relationship."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    await async_session.refresh(token_balance)
    await async_session.refresh(test_user)

    assert token_balance.user is not None
    assert token_balance.user.id == test_user.id
    assert token_balance == test_user.token_balance_record
    assert token_balance == test_user.token_balance

@pytest.mark.no_token_balance
@pytest.mark.asyncio
async def test_concurrent_balance_updates(async_session: AsyncSession, test_user):
    """Test concurrent balance updates."""
    # Delete any existing token balance
    await async_session.execute(
        text("DELETE FROM token_balances WHERE user_id = :user_id"),
        {"user_id": test_user.id}
    )
    await async_session.commit()

    # Create initial balance
    balance = TokenBalance(user_id=test_user.id, balance=Decimal("100.0"))
    async_session.add(balance)
    await async_session.commit()

    # Create two separate sessions for concurrent updates
    async with AsyncSession(async_session.bind) as session1, \
             AsyncSession(async_session.bind) as session2:
        
        # Start transactions in both sessions
        await session1.begin()
        await session2.begin()

        # Update balance in first session
        await session1.execute(
            text("""
                UPDATE token_balances 
                SET balance = balance - :amount 
                WHERE user_id = :user_id 
                RETURNING balance
            """),
            {"amount": Decimal("25.0"), "user_id": str(test_user.id)}
        )
        await session1.commit()

        # Update balance in second session
        await session2.execute(
            text("""
                UPDATE token_balances 
                SET balance = balance - :amount 
                WHERE user_id = :user_id 
                RETURNING balance
            """),
            {"amount": Decimal("25.0"), "user_id": str(test_user.id)}
        )
        await session2.commit()

    # Verify final balance
    await async_session.refresh(balance)
    assert balance.balance == Decimal("50.0")

@pytest.mark.asyncio
async def test_transaction_rollback(async_session: AsyncSession, test_user: User):
    """Test transaction rollback."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    initial_balance = token_balance.balance
    initial_updated_at = token_balance.updated_at

    try:
        async with async_session.begin_nested():
            # First update should succeed
            await token_balance.update_balance(
                db=async_session,
                amount=Decimal("30.0"),
                operation=TransactionType.DEDUCTION.value,
                reason="First deduction"
            )
            
            # Second update should fail and trigger rollback
            await token_balance.update_balance(
                db=async_session,
                amount=Decimal("80.0"),
                operation=TransactionType.DEDUCTION.value,
                reason="Second deduction"
            )
    except InsufficientBalanceError:
        pass
    
    await async_session.refresh(token_balance)
    assert token_balance.balance == initial_balance
    assert token_balance.updated_at == initial_updated_at

    # Check no history records were created
    stmt = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == token_balance.id)
    result = await async_session.execute(stmt)
    assert result.first() is None

@pytest.mark.asyncio
async def test_history_relationship(async_session: AsyncSession, test_user: User):
    """Test token balance history relationship."""
    token_balance = await async_session.get(TokenBalance, test_user.token_balance.id)
    
    async with async_session.begin_nested():
        # Create some history records
        await token_balance.update_balance(
            db=async_session,
            amount=Decimal("50.0"),
            operation=TransactionType.DEDUCTION.value,
            reason="First deduction"
        )
        
        await token_balance.update_balance(
            db=async_session,
            amount=Decimal("30.0"),
            operation=TransactionType.REWARD.value,
            reason="First reward"
        )
    
    await async_session.refresh(token_balance)
    assert len(token_balance.history) == 2
    
    # Check history records
    history = sorted(token_balance.history, key=lambda x: x.created_at)
    assert history[0].change_type == TransactionType.DEDUCTION.value
    assert history[0].change_amount == Decimal("50.0")
    assert history[1].change_type == TransactionType.REWARD.value
    assert history[1].change_amount == Decimal("30.0")

@pytest.mark.no_token_balance
@pytest.mark.asyncio
async def test_unique_user_constraint(async_session: AsyncSession, test_user: User):
    """Test unique constraint on user_id."""
    # Delete any existing token balance
    await async_session.execute(
        text("DELETE FROM token_balances WHERE user_id = :user_id"),
        {"user_id": test_user.id}
    )
    await async_session.commit()

    # Create first token balance
    balance1 = TokenBalance(user_id=test_user.id, balance=Decimal("100.0"))
    async_session.add(balance1)
    await async_session.commit()

    # Try to create second token balance for same user
    balance2 = TokenBalance(user_id=test_user.id, balance=Decimal("50.0"))
    async_session.add(balance2)
    
    # This should raise an IntegrityError due to unique constraint
    with pytest.raises(IntegrityError):
        await async_session.commit()
    
    # Clean up
    await async_session.rollback()
    await async_session.delete(balance1)
    await async_session.commit()

@pytest.mark.no_token_balance
@pytest.mark.asyncio
async def test_zero_balance_validation(async_session: AsyncSession, test_user):
    """Test that zero balance is allowed."""
    # Delete any existing token balance
    await async_session.execute(
        text("DELETE FROM token_balances WHERE user_id = :user_id"),
        {"user_id": test_user.id}
    )
    await async_session.commit()

    balance = TokenBalance(user_id=test_user.id, balance=Decimal("0.0"))
    async_session.add(balance)
    await async_session.commit()
    assert balance.balance == Decimal("0.00000000")

@pytest.mark.no_token_balance
@pytest.mark.asyncio
async def test_decimal_precision(async_session: AsyncSession, test_user):
    """Test decimal precision handling."""
    # Delete any existing token balance
    await async_session.execute(
        text("DELETE FROM token_balances WHERE user_id = :user_id"),
        {"user_id": test_user.id}
    )
    await async_session.commit()

    balance = TokenBalance(user_id=test_user.id, balance=Decimal("100.12345678"))
    async_session.add(balance)
    await async_session.commit()

    await balance.update_balance(
        db=async_session,
        amount=Decimal("50.87654321"),
        operation=TransactionType.REWARD.value,
        reason="Test reward"
    )
    await async_session.refresh(balance)
    
    # Calculate expected balance with proper rounding
    expected_balance = (Decimal("100.12345678") + Decimal("50.87654321")).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
    assert balance.balance == expected_balance

@pytest.mark.no_token_balance
@pytest.mark.asyncio
async def test_large_number_handling(async_session: AsyncSession, test_user):
    """Test handling of large numbers."""
    # Delete any existing token balance
    await async_session.execute(
        text("DELETE FROM token_balances WHERE user_id = :user_id"),
        {"user_id": test_user.id}
    )
    await async_session.commit()

    balance = TokenBalance(user_id=test_user.id, balance=Decimal("1000000000.00000000"))
    async_session.add(balance)
    await async_session.commit()

    await balance.update_balance(
        db=async_session,
        amount=Decimal("999999999.00000000"),
        operation=TransactionType.DEDUCTION.value,
        reason="Test large deduction"
    )
    await async_session.refresh(balance)
    assert balance.balance == Decimal("1.00000000")

@pytest.mark.no_token_balance
@pytest.mark.asyncio
async def test_multiple_operations_atomicity(async_session: AsyncSession, test_user):
    """Test atomicity of multiple operations."""
    # Delete any existing token balance
    await async_session.execute(
        text("DELETE FROM token_balances WHERE user_id = :user_id"),
        {"user_id": test_user.id}
    )
    await async_session.commit()

    # Create initial balance
    balance = TokenBalance(user_id=test_user.id, balance=Decimal("100.0"))
    async_session.add(balance)
    await async_session.commit()

    # Perform multiple operations in a single transaction
    async with async_session.begin_nested():
        await balance.update_balance(
            db=async_session,
            amount=Decimal("25.0"),
            operation=TransactionType.DEDUCTION.value,
            reason="Test deduction"
        )
        await balance.update_balance(
            db=async_session,
            amount=Decimal("50.0"),
            operation=TransactionType.REWARD.value,
            reason="Test reward"
        )
        await balance.update_balance(
            db=async_session,
            amount=Decimal("10.0"),
            operation=TransactionType.REFUND.value,
            reason="Test refund"
        )

    await async_session.commit()
    await async_session.refresh(balance)

    # Verify final balance
    expected_balance = (Decimal("100.0") - Decimal("25.0") + Decimal("50.0") + Decimal("10.0")).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
    assert balance.balance == expected_balance

    # Verify history records
    stmt = select(TokenBalanceHistory).where(TokenBalanceHistory.token_balance_id == balance.id)
    result = await async_session.execute(stmt)
    history_records = result.scalars().all()
    assert len(history_records) == 3
    assert history_records[0].change_type == TransactionType.DEDUCTION.value
    assert history_records[1].change_type == TransactionType.REWARD.value
    assert history_records[2].change_type == TransactionType.REFUND.value

@pytest.mark.asyncio
async def test_update_balance_reward(db_session):
    """Test updating balance with reward."""
    # Create initial balance
    balance = TokenBalance(
        user_id=uuid4(),
        balance=Decimal("100.0")
    )
    db_session.add(balance)
    await db_session.commit()

    # Add reward
    await balance.update_balance(
        db_session,
        Decimal("50.0"),
        TransactionType.REWARD.value,
        "Test reward"
    )

    assert balance.balance == Decimal("150.0")

@pytest.mark.asyncio
async def test_update_balance_deduction(db_session):
    """Test updating balance with deduction."""
    # Create initial balance
    balance = TokenBalance(
        user_id=uuid4(),
        balance=Decimal("100.0")
    )
    db_session.add(balance)
    await db_session.commit()

    # Deduct tokens
    await balance.update_balance(
        db_session,
        Decimal("50.0"),
        TransactionType.DEDUCTION.value,
        "Test deduction"
    )

    assert balance.balance == Decimal("50.0")

@pytest.mark.asyncio
async def test_insufficient_balance(db_session):
    """Test deduction with insufficient balance."""
    # Create initial balance
    balance = TokenBalance(
        user_id=uuid4(),
        balance=Decimal("100.0")
    )
    db_session.add(balance)
    await db_session.commit()

    # Try to deduct more than available
    with pytest.raises(InsufficientBalanceError):
        await balance.update_balance(
            db_session,
            Decimal("150.0"),
            TransactionType.DEDUCTION.value,
            "Test deduction"
        )

@pytest.mark.asyncio
async def test_invalid_operation(db_session):
    """Test invalid operation type."""
    # Create initial balance
    balance = TokenBalance(
        user_id=uuid4(),
        balance=Decimal("100.0")
    )
    db_session.add(balance)
    await db_session.commit()

    # Try invalid operation
    with pytest.raises(ValueError):
        await balance.update_balance(
            db_session,
            Decimal("50.0"),
            "invalid_operation",
            "Test invalid"
        ) 