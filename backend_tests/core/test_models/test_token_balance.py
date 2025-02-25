import pytest
from decimal import Decimal, ROUND_DOWN
from uuid import UUID
from sqlalchemy import select
from core.models.user import User
from core.models.token_models import TokenTransaction
from core.models.enums import TokenTransactionType, TokenTransactionStatus
from backend_tests.factories.user import UserFactory
from backend_tests.factories.token import TokenTransactionFactory
from backend_tests.utils.markers import core_test

pytestmark = pytest.mark.asyncio

@core_test
async def test_token_transaction_creation(db_session):
    """Test creating a token transaction."""
    # Create a user first
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create a token transaction
    transaction = await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=Decimal("10.0"),
        type=TokenTransactionType.REWARD.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    # Verify transaction was created
    assert transaction.id is not None
    assert isinstance(transaction.id, UUID)
    assert transaction.amount == Decimal("10.0")
    assert transaction.type == TokenTransactionType.REWARD.value
    assert transaction.status == TokenTransactionStatus.COMPLETED.value
    assert transaction.user_id == user.id
    
    # Verify transaction exists in database
    stmt = select(TokenTransaction).where(TokenTransaction.id == transaction.id)
    result = await db_session.execute(stmt)
    db_transaction = result.scalar_one()
    
    assert db_transaction.id == transaction.id
    assert db_transaction.amount == Decimal("10.0")
    assert db_transaction.type == TokenTransactionType.REWARD.value
    assert db_transaction.status == TokenTransactionStatus.COMPLETED.value
    assert db_transaction.user_id == user.id

@core_test
async def test_user_token_balance(db_session):
    """Test user token balance updates."""
    # Create a user
    user = await UserFactory.create_async(db_session=db_session)
    initial_balance = await user.get_token_balance(db_session)
    
    # Create a reward transaction
    reward_amount = Decimal("50.0")
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=reward_amount,
        type=TokenTransactionType.REWARD.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    # Get updated balance
    new_balance = await user.get_token_balance(db_session)
    assert new_balance == initial_balance + reward_amount
    
    # Create a deduction transaction
    deduction_amount = Decimal("20.0")
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=deduction_amount,
        type=TokenTransactionType.DEDUCTION.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    # Get final balance
    final_balance = await user.get_token_balance(db_session)
    assert final_balance == initial_balance + reward_amount - deduction_amount

@core_test
async def test_token_transaction_validation(db_session):
    """Test token transaction validation."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Test invalid amount
    with pytest.raises(ValueError):
        await TokenTransactionFactory.create_async(
            db_session=db_session,
            user=user,
            amount=Decimal("-10.0"),  # Negative amount should fail
            type=TokenTransactionType.REWARD.value
        )
    
    # Test invalid type
    with pytest.raises(ValueError):
        await TokenTransactionFactory.create_async(
            db_session=db_session,
            user=user,
            amount=Decimal("10.0"),
            type="invalid_type"  # Invalid type should fail
        )
    
    # Test invalid status
    with pytest.raises(ValueError):
        await TokenTransactionFactory.create_async(
            db_session=db_session,
            user=user,
            amount=Decimal("10.0"),
            type=TokenTransactionType.REWARD.value,
            status="invalid_status"  # Invalid status should fail
        )

@core_test
async def test_token_balance_precision(db_session):
    """Test token balance precision handling."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Test small amounts
    small_amount = Decimal("0.00000001")  # 8 decimal places
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=small_amount,
        type=TokenTransactionType.REWARD.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    balance = await user.get_token_balance(db_session)
    assert balance == small_amount.quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
    
    # Test large amounts with a value that won't cause precision issues
    large_amount = Decimal("1000000000.00000000")  # Large number with exact precision
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=large_amount,
        type=TokenTransactionType.REWARD.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    balance = await user.get_token_balance(db_session)
    expected_balance = (small_amount + large_amount).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
    assert balance == expected_balance
    
    # Test exact precision with another small amount
    another_small_amount = Decimal("0.00000001")
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=another_small_amount,
        type=TokenTransactionType.REWARD.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    balance = await user.get_token_balance(db_session)
    expected_balance = (small_amount + large_amount + another_small_amount).quantize(Decimal('0.00000000'), rounding=ROUND_DOWN)
    assert balance == expected_balance 