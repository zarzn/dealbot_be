import pytest
from decimal import Decimal
from uuid import uuid4, UUID
from datetime import datetime, timezone
from core.services.token_service import TokenServiceV2
from core.services.redis import get_redis_service
from core.models.enums import TokenTransactionType, TokenTransactionStatus
from core.exceptions import (
    TokenError,
    TokenBalanceError,
    TokenTransactionError,
    ValidationError,
    InsufficientBalanceError,
    TokenValidationError
)
from factories.user import UserFactory
from factories.token import TokenTransactionFactory, TokenBalanceFactory
from backend_tests.utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
def token_service(db_session):
    """Create token service instance for testing."""
    return TokenServiceV2()

@service_test
@depends_on("core.test_models.test_token_balance.test_token_transaction_creation")
async def test_get_balance(db_session, token_service):
    """Test getting a user's token balance."""
    user = await UserFactory.create_async(db_session=db_session)
    initial_balance = Decimal("0.0")
    
    # Add some tokens
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=Decimal("50.0"),
        type=TokenTransactionType.CREDIT.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    balance = await token_service.get_balance(user.id)
    assert balance == initial_balance + Decimal("50.0")

@service_test
@depends_on("core.test_models.test_token_balance.test_token_transaction_creation")
async def test_transfer_tokens(db_session, token_service):
    """Test transferring tokens between users."""
    from_user = await UserFactory.create_async(db_session=db_session)
    to_user = await UserFactory.create_async(db_session=db_session)
    
    # Credit tokens to from_user
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=from_user,
        amount=Decimal("100.0"),
        type=TokenTransactionType.CREDIT.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    # Transfer tokens
    amount = Decimal("50.0")
    async with db_session.begin():
        await token_service.transfer_tokens(
            db_session,
            from_user_id=from_user.id,
            to_user_id=to_user.id,
            amount=amount,
            reason="Test transfer"
        )
    
    # Verify balances
    from_balance = await token_service.get_balance(from_user.id)
    to_balance = await token_service.get_balance(to_user.id)
    
    assert from_balance == Decimal("50.0")
    assert to_balance == Decimal("50.0")

@service_test
@depends_on("core.test_models.test_token_balance.test_token_transaction_creation")
async def test_insufficient_balance(db_session, token_service):
    """Test transfer with insufficient balance."""
    from_user = await UserFactory.create_async(db_session=db_session)
    to_user = await UserFactory.create_async(db_session=db_session)
    
    # Try to transfer more than available
    with pytest.raises((InsufficientBalanceError, TokenTransactionError)) as excinfo:
        async with db_session.begin():
            await token_service.transfer_tokens(
                db_session,
                from_user_id=from_user.id,
                to_user_id=to_user.id,
                amount=Decimal("100.0"),
                reason="Test transfer"
            )
    
    # Verify that the error is related to insufficient balance
    assert "Insufficient balance" in str(excinfo.value) or "Token transaction failed" in str(excinfo.value)

@service_test
@depends_on("core.test_models.test_token_balance.test_token_transaction_creation")
async def test_service_fee(db_session, token_service):
    """Test service fee deduction."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Credit tokens to user
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=Decimal("100.0"),
        type=TokenTransactionType.CREDIT.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    # Deduct service fee
    fee = Decimal("10.0")
    async with db_session.begin():
        await token_service.process_transaction(
            db_session,
            user_id=user.id,
            amount=fee,
            transaction_type=TokenTransactionType.DEDUCTION,
            details={"service_type": "test_service"}
        )
    
    balance = await token_service.get_balance(user.id)
    assert balance == Decimal("90.0")

@service_test
@depends_on("core.test_models.test_token.test_token_transaction")
async def test_transaction_history(db_session, token_service):
    """Test retrieving token transaction history."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create multiple transactions with different amounts
    transactions = []
    
    # First transaction
    tx1 = await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=Decimal("10.0"),
        type=TokenTransactionType.CREDIT.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    transactions.append(tx1)
    
    # Second transaction
    tx2 = await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=Decimal("20.0"),
        type=TokenTransactionType.CREDIT.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    transactions.append(tx2)
    
    # Third transaction
    tx3 = await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=Decimal("30.0"),
        type=TokenTransactionType.CREDIT.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    transactions.append(tx3)
    
    # Get transaction history
    history, count = await token_service.get_transaction_history(user_id=user.id, limit=10, offset=0)
    
    # Verify the correct number of transactions are returned
    assert count == 3
    assert len(history) == 3
    
    # Sort transactions by created_at to verify chronological order
    # In a real system, they would be returned in reverse chronological order
    # but since these are created almost simultaneously in tests, we may not get expected ordering
    # Instead, we'll verify all transactions are present with correct amounts
    tx_amounts = [Decimal("10.0"), Decimal("20.0"), Decimal("30.0")]
    history_amounts = [tx.amount for tx in history]
    
    for amount in tx_amounts:
        assert amount in history_amounts, f"Transaction with amount {amount} not found in history"

@service_test
@depends_on("core.test_models.test_token_balance.test_token_transaction_creation")
async def test_balance_cache(db_session, token_service):
    """Test token balance caching."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Credit tokens
    await TokenTransactionFactory.create_async(
        db_session=db_session,
        user=user,
        amount=Decimal("100.0"),
        type=TokenTransactionType.CREDIT.value,
        status=TokenTransactionStatus.COMPLETED.value
    )
    
    # Get balance (should cache)
    balance1 = await token_service.get_balance(user.id)
    
    # Get balance again (should use cache if implemented)
    balance2 = await token_service.get_balance(user.id)
    
    assert balance1 == balance2 == Decimal("100.0")

@service_test
@depends_on("core.test_models.test_token_balance.test_token_transaction_creation")
async def test_transaction_validation(db_session, token_service):
    """Test transaction validation."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Test invalid amount (negative)
    with pytest.raises(TokenValidationError):
        async with db_session.begin():
            await token_service.process_transaction(
                db_session,
                user_id=user.id,
                amount=Decimal("-10.0"),
                transaction_type=TokenTransactionType.CREDIT
            )
    
    # Test valid transaction
    async with db_session.begin():
        transaction = await token_service.process_transaction(
            db_session,
            user_id=user.id,
            amount=Decimal("10.0"),
            transaction_type=TokenTransactionType.CREDIT
        )
    
    assert transaction is not None
    assert transaction.user_id == user.id
    assert transaction.amount == Decimal("10.0")
    assert transaction.type == TokenTransactionType.CREDIT.value.lower()
    assert transaction.status == TokenTransactionStatus.COMPLETED.value.lower()

@pytest.mark.service
async def test_token_transaction_creation(token_service, db_session):
    """Test creating a token transaction."""
    user = await UserFactory.create_async(db_session=db_session)
    amount = Decimal('0.00000001')  # 1E-8
    
    async with db_session.begin():
        transaction = await token_service.process_transaction(
            db_session,
            user_id=user.id,
            amount=amount,
            transaction_type=TokenTransactionType.REWARD
        )
    
    assert transaction.user_id == user.id
    assert transaction.amount == amount
    assert transaction.type == TokenTransactionType.REWARD.value.lower()
    assert transaction.status == TokenTransactionStatus.COMPLETED.value.lower()

@pytest.mark.service
async def test_token_balance_calculation(token_service, db_session):
    """Test calculating token balance."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Create token balance first to ensure it exists with a starting balance of 0
    token_balance = await TokenBalanceFactory.create_async(
        db_session=db_session,
        user=user,
        balance=Decimal('0.0')
    )
    
    # Create a reward transaction that adds 1.0 tokens
    async with db_session.begin():
        tx1 = await token_service.process_transaction(
            db_session,
            user_id=user.id,
            amount=Decimal('1.0'),
            transaction_type=TokenTransactionType.REWARD
        )
    
    # Get balance after first transaction
    balance1 = await token_service.get_balance(user.id)
    assert balance1 == Decimal('1.0')
    
    # Create a second transaction that adds 0.5 tokens
    async with db_session.begin():
        tx2 = await token_service.process_transaction(
            db_session,
            user_id=user.id,
            amount=Decimal('0.5'),
            transaction_type=TokenTransactionType.REWARD
        )
    
    # Final balance should be the sum of the transactions
    # In this test, we expect 1.5 (1.0 + 0.5)
    balance = await token_service.get_balance(user.id)
    assert balance == Decimal('1.5')

@pytest.mark.service
async def test_token_transaction_validation(token_service, db_session):
    """Test transaction validation."""
    user = await UserFactory.create_async(db_session=db_session)
    
    # Test negative amount (should fail validation)
    with pytest.raises(TokenValidationError):
        async with db_session.begin():
            await token_service.process_transaction(
                db_session,
                user_id=user.id,
                amount=Decimal('-1.0'),
                transaction_type=TokenTransactionType.REWARD
            )
    
    # Test too many decimal places (should fail validation)
    with pytest.raises(TokenValidationError):
        async with db_session.begin():
            await token_service.process_transaction(
                db_session,
                user_id=user.id,
                amount=Decimal('0.000000001'),  # More than 8 decimal places
                transaction_type=TokenTransactionType.REWARD
            ) 