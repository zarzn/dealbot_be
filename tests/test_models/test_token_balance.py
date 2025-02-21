"""Token balance model tests."""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from core.database import AsyncSessionLocal
from core.models.token_balance import TokenBalance
from core.models.token_balance_history import TokenBalanceHistory, BalanceChangeType
from core.exceptions.token_exceptions import (
    TokenError,
    TokenBalanceError,
    InsufficientBalanceError,
    InvalidBalanceChangeError as InvalidBalanceError
)

@pytest.mark.asyncio
async def test_create_token_balance(async_session: AsyncSession, test_user):
    """Test creating a token balance."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    
    async_session.add(token_balance)
    await async_session.commit()
    await async_session.refresh(token_balance)
    
    assert token_balance.id is not None
    assert token_balance.user_id == test_user.id
    assert token_balance.balance == Decimal("100.0")
    assert token_balance.created_at is not None
    assert token_balance.updated_at is not None

@pytest.mark.asyncio
async def test_update_balance_deduction(async_session: AsyncSession, test_user):
    """Test deducting from token balance."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    before_update = token_balance.updated_at
    await asyncio.sleep(1)  # Ensure time difference

    await token_balance.update_balance(
        db=async_session,
        amount=Decimal("50.0"),
        operation=BalanceChangeType.DEDUCTION.value,
        reason="Test deduction"
    )

    assert token_balance.balance == Decimal("50.0")
    assert token_balance.updated_at > before_update

@pytest.mark.asyncio
async def test_update_balance_reward(async_session: AsyncSession, test_user):
    """Test adding reward to token balance."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    before_update = token_balance.updated_at
    await asyncio.sleep(1)  # Ensure time difference

    await token_balance.update_balance(
        db=async_session,
        amount=Decimal("50.0"),
        operation=BalanceChangeType.REWARD.value,
        reason="Test reward"
    )

    assert token_balance.balance == Decimal("150.0")
    assert token_balance.updated_at > before_update

@pytest.mark.asyncio
async def test_insufficient_balance_error(async_session: AsyncSession, test_user):
    """Test insufficient balance error."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    initial_balance = token_balance.balance
    initial_updated_at = token_balance.updated_at

    with pytest.raises(InsufficientBalanceError, match="Insufficient balance for deduction"):
        await token_balance.update_balance(
            db=async_session,
            amount=Decimal("150.0"),
            operation=BalanceChangeType.DEDUCTION.value,
            reason="Test insufficient balance"
        )

    # Balance and timestamp should remain unchanged
    assert token_balance.balance == initial_balance
    assert token_balance.updated_at == initial_updated_at

@pytest.mark.asyncio
async def test_invalid_operation_error(async_session: AsyncSession, test_user):
    """Test invalid operation error."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    initial_balance = token_balance.balance
    initial_updated_at = token_balance.updated_at

    with pytest.raises(InvalidBalanceError, match="Invalid operation type"):
        await token_balance.update_balance(
            db=async_session,
            amount=Decimal("50.0"),
            operation="invalid_operation",
            reason="Test invalid operation"
        )

    # Balance and timestamp should remain unchanged
    assert token_balance.balance == initial_balance
    assert token_balance.updated_at == initial_updated_at

@pytest.mark.asyncio
async def test_negative_balance_validation(async_session: AsyncSession, test_user):
    """Test that negative balance is not allowed."""
    with pytest.raises(InvalidBalanceError, match="Balance cannot be negative"):
        token_balance = TokenBalance(
            user_id=test_user.id,
            balance=Decimal("-100.0")
        )
        async_session.add(token_balance)
        await async_session.commit()

@pytest.mark.asyncio
async def test_refund_operation(async_session: AsyncSession, test_user):
    """Test refund operation."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    before_update = token_balance.updated_at
    await asyncio.sleep(1)  # Ensure time difference

    await token_balance.update_balance(
        db=async_session,
        amount=Decimal("50.0"),
        operation=BalanceChangeType.REFUND.value,
        reason="Test refund"
    )

    assert token_balance.balance == Decimal("150.0")
    assert token_balance.updated_at > before_update

@pytest.mark.asyncio
async def test_user_relationship(async_session: AsyncSession, test_user):
    """Test user relationship."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()
    await async_session.refresh(token_balance)

    assert token_balance.user is not None
    assert token_balance.user.id == test_user.id
    assert token_balance == test_user.token_balance_record

@pytest.mark.asyncio
async def test_concurrent_balance_updates(async_session: AsyncSession, test_user):
    """Test concurrent balance updates."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    # Create two concurrent updates
    async def update_1():
        async with AsyncSessionLocal() as session1:
            balance1 = await session1.get(TokenBalance, token_balance.id)
            await balance1.update_balance(
                db=session1,
                amount=Decimal("30.0"),
                operation=BalanceChangeType.DEDUCTION.value,
                reason="Concurrent deduction 1"
            )

    async def update_2():
        async with AsyncSessionLocal() as session2:
            balance2 = await session2.get(TokenBalance, token_balance.id)
            await balance2.update_balance(
                db=session2,
                amount=Decimal("20.0"),
                operation=BalanceChangeType.DEDUCTION.value,
                reason="Concurrent deduction 2"
            )

    # Run updates concurrently
    await asyncio.gather(update_1(), update_2())

    # Refresh and check final balance
    await async_session.refresh(token_balance)
    assert token_balance.balance == Decimal("50.0")  # 100 - 30 - 20

@pytest.mark.asyncio
async def test_transaction_rollback(async_session: AsyncSession, test_user):
    """Test transaction rollback on error."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    initial_balance = token_balance.balance
    initial_updated_at = token_balance.updated_at

    try:
        async with async_session.begin():
            # First update should succeed
            await token_balance.update_balance(
                db=async_session,
                amount=Decimal("30.0"),
                operation=BalanceChangeType.DEDUCTION.value,
                reason="First deduction"
            )
            
            # Second update should fail and trigger rollback
            await token_balance.update_balance(
                db=async_session,
                amount=Decimal("80.0"),  # Would make balance negative
                operation=BalanceChangeType.DEDUCTION.value,
                reason="Second deduction"
            )
    except InsufficientBalanceError:
        pass

    # Refresh and verify balance was rolled back
    await async_session.refresh(token_balance)
    assert token_balance.balance == initial_balance
    assert token_balance.updated_at == initial_updated_at

@pytest.mark.asyncio
async def test_history_relationship(async_session: AsyncSession, test_user):
    """Test token balance history relationship."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    # Perform some operations to generate history
    await token_balance.update_balance(
        db=async_session,
        amount=Decimal("30.0"),
        operation=BalanceChangeType.DEDUCTION.value,
        reason="Test deduction"
    )
    
    await token_balance.update_balance(
        db=async_session,
        amount=Decimal("50.0"),
        operation=BalanceChangeType.REWARD.value,
        reason="Test reward"
    )

    await async_session.refresh(token_balance)
    
    # Check history records
    assert len(token_balance.history) == 2
    
    deduction = token_balance.history[0]
    assert deduction.balance_before == Decimal("100.0")
    assert deduction.balance_after == Decimal("70.0")
    assert deduction.change_amount == Decimal("30.0")
    assert deduction.change_type == BalanceChangeType.DEDUCTION
    assert deduction.reason == "Test deduction"
    assert deduction.created_at is not None
    
    reward = token_balance.history[1]
    assert reward.balance_before == Decimal("70.0")
    assert reward.balance_after == Decimal("120.0")
    assert reward.change_amount == Decimal("50.0")
    assert reward.change_type == BalanceChangeType.REWARD
    assert reward.reason == "Test reward"
    assert reward.created_at is not None

@pytest.mark.asyncio
async def test_unique_user_constraint(async_session: AsyncSession, test_user):
    """Test that each user can have only one token balance."""
    token_balance1 = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance1)
    await async_session.commit()

    # Try to create another balance for the same user
    with pytest.raises(IntegrityError):
        token_balance2 = TokenBalance(
            user_id=test_user.id,
            balance=Decimal("200.0")
        )
        async_session.add(token_balance2)
        await async_session.commit()

@pytest.mark.asyncio
async def test_decimal_precision(async_session: AsyncSession, test_user):
    """Test decimal precision handling."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.12345678")  # 8 decimal places
    )
    async_session.add(token_balance)
    await async_session.commit()
    await async_session.refresh(token_balance)

    assert token_balance.balance == Decimal("100.12345678")

    # Test precision in operations
    await token_balance.update_balance(
        db=async_session,
        amount=Decimal("50.87654321"),
        operation=BalanceChangeType.REWARD.value,
        reason="Test precision"
    )

    assert token_balance.balance == Decimal("150.99999999")

@pytest.mark.asyncio
async def test_cascade_delete(async_session: AsyncSession, test_user):
    """Test that history is deleted when balance is deleted."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    # Create some history
    await token_balance.update_balance(
        db=async_session,
        amount=Decimal("50.0"),
        operation=BalanceChangeType.DEDUCTION.value,
        reason="Test cascade"
    )

    # Delete balance
    await async_session.delete(token_balance)
    await async_session.commit()

    # Verify history was deleted
    history = await async_session.query(TokenBalanceHistory).filter(
        TokenBalanceHistory.user_id == test_user.id
    ).all()
    assert len(history) == 0

@pytest.mark.asyncio
async def test_large_number_handling(async_session: AsyncSession, test_user):
    """Test handling of large numbers."""
    large_amount = Decimal("1000000000.00000000")  # 1 billion with 8 decimals
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=large_amount
    )
    async_session.add(token_balance)
    await async_session.commit()
    await async_session.refresh(token_balance)

    assert token_balance.balance == large_amount

    # Test large deduction
    await token_balance.update_balance(
        db=async_session,
        amount=Decimal("999999999.99999999"),
        operation=BalanceChangeType.DEDUCTION.value,
        reason="Large deduction"
    )

    assert token_balance.balance == Decimal("0.00000001")

@pytest.mark.asyncio
async def test_multiple_operations_atomicity(async_session: AsyncSession, test_user):
    """Test atomicity of multiple operations."""
    token_balance = TokenBalance(
        user_id=test_user.id,
        balance=Decimal("100.0")
    )
    async_session.add(token_balance)
    await async_session.commit()

    operations = [
        (Decimal("30.0"), BalanceChangeType.DEDUCTION.value, "First deduction"),
        (Decimal("50.0"), BalanceChangeType.REWARD.value, "First reward"),
        (Decimal("20.0"), BalanceChangeType.DEDUCTION.value, "Second deduction"),
        (Decimal("10.0"), BalanceChangeType.REFUND.value, "First refund")
    ]

    async with async_session.begin():
        for amount, operation, reason in operations:
            await token_balance.update_balance(
                db=async_session,
                amount=amount,
                operation=operation,
                reason=reason
            )

    await async_session.refresh(token_balance)
    assert token_balance.balance == Decimal("110.0")  # 100 - 30 + 50 - 20 + 10
    assert len(token_balance.history) == len(operations) 