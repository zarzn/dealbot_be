"""Tests for database operations and model interactions."""

import pytest
import uuid
import datetime
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from core.models.base import Base
from core.models.user import User
from core.models.deal import Deal
from core.models.market import Market
from core.models.token import Token
from core.models.goal import Goal
from core.models.enums import DealStatus, MarketType, TokenStatus, GoalStatus

@pytest.mark.asyncio
@pytest.mark.core
async def test_user_creation(db_session):
    """Test creating a user in the database."""
    # Create a new user
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password="hashed_password_value",
        is_active=True,
        is_superuser=False
    )
    
    # Add to session and commit
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Verify the user was created with an ID
    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.email == "test@example.com"
    assert user.username == "testuser"
    assert user.full_name == "Test User"
    assert user.is_active is True
    assert user.is_superuser is False
    
    # Verify created_at and updated_at were set
    assert user.created_at is not None
    assert user.updated_at is not None
    assert isinstance(user.created_at, datetime.datetime)
    assert isinstance(user.updated_at, datetime.datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_user_unique_constraints(db_session):
    """Test unique constraints on the user model."""
    # Create a user
    user1 = User(
        email="unique@example.com",
        username="uniqueuser",
        full_name="Unique User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user1)
    await db_session.commit()
    
    # Try to create another user with the same email
    user2 = User(
        email="unique@example.com",  # Same email
        username="differentuser",
        full_name="Different User",
        hashed_password="different_hashed_password",
        is_active=True
    )
    db_session.add(user2)
    
    # Should raise an integrity error due to unique constraint
    with pytest.raises(IntegrityError):
        await db_session.commit()
    
    # Rollback the failed transaction
    await db_session.rollback()
    
    # Try to create another user with the same username
    user3 = User(
        email="different@example.com",
        username="uniqueuser",  # Same username
        full_name="Another User",
        hashed_password="another_hashed_password",
        is_active=True
    )
    db_session.add(user3)
    
    # Should raise an integrity error due to unique constraint
    with pytest.raises(IntegrityError):
        await db_session.commit()
    
    # Rollback the failed transaction
    await db_session.rollback()

@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_creation_and_relationships(db_session):
    """Test creating a deal with relationships to other models."""
    # Create a user
    user = User(
        email="deal_test@example.com",
        username="dealuser",
        full_name="Deal Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a market
    market = Market(
        name="Test Market",
        description="A test market for deal relationships",
        type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a deal linked to the user and market
    deal = Deal(
        title="Test Deal",
        description="A test deal with relationships",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        market_id=market.id,
        metadata={"priority": "high"}
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    
    # Create goals for the deal
    goal1 = Goal(
        title="Goal 1",
        description="First test goal",
        status=GoalStatus.PENDING.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        priority=1
    )
    
    goal2 = Goal(
        title="Goal 2",
        description="Second test goal",
        status=GoalStatus.PENDING.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        priority=2
    )
    
    db_session.add_all([goal1, goal2])
    await db_session.commit()
    
    # Create tokens for the deal
    token1 = Token(
        name="Token 1",
        symbol="TK1",
        status=TokenStatus.ACTIVE.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        metadata={"decimals": 18}
    )
    
    token2 = Token(
        name="Token 2",
        symbol="TK2",
        status=TokenStatus.ACTIVE.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        metadata={"decimals": 6}
    )
    
    db_session.add_all([token1, token2])
    await db_session.commit()
    
    # Refresh the deal to load relationships
    await db_session.refresh(deal)
    
    # Test relationship loading via query
    stmt = select(Deal).where(Deal.id == deal.id)
    result = await db_session.execute(stmt)
    loaded_deal = result.scalar_one()
    
    # Verify the deal was created with relationships
    assert loaded_deal.id == deal.id
    assert loaded_deal.user_id == user.id
    assert loaded_deal.market_id == market.id
    
    # Load and verify goals relationship
    stmt = select(Goal).where(Goal.deal_id == deal.id).order_by(Goal.priority)
    result = await db_session.execute(stmt)
    goals = result.scalars().all()
    
    assert len(goals) == 2
    assert goals[0].title == "Goal 1"
    assert goals[1].title == "Goal 2"
    
    # Load and verify tokens relationship
    stmt = select(Token).where(Token.deal_id == deal.id).order_by(Token.symbol)
    result = await db_session.execute(stmt)
    tokens = result.scalars().all()
    
    assert len(tokens) == 2
    assert tokens[0].symbol == "TK1"
    assert tokens[1].symbol == "TK2"

@pytest.mark.asyncio
@pytest.mark.core
async def test_cascade_delete(db_session):
    """Test cascade delete behavior for related models."""
    # Create a user
    user = User(
        email="cascade@example.com",
        username="cascadeuser",
        full_name="Cascade Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Cascade Test Deal",
        description="A deal to test cascade delete",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create goals for the deal
    goal1 = Goal(
        title="Cascade Goal 1",
        description="First cascade test goal",
        status=GoalStatus.PENDING.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        priority=1
    )
    
    goal2 = Goal(
        title="Cascade Goal 2",
        description="Second cascade test goal",
        status=GoalStatus.PENDING.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        priority=2
    )
    
    db_session.add_all([goal1, goal2])
    await db_session.commit()
    
    # Create tokens for the deal
    token1 = Token(
        name="Cascade Token 1",
        symbol="CTK1",
        status=TokenStatus.ACTIVE.value.lower(),
        deal_id=deal.id,
        user_id=user.id
    )
    
    token2 = Token(
        name="Cascade Token 2",
        symbol="CTK2",
        status=TokenStatus.ACTIVE.value.lower(),
        deal_id=deal.id,
        user_id=user.id
    )
    
    db_session.add_all([token1, token2])
    await db_session.commit()
    
    # Verify the related records exist
    goal_count_stmt = select(func.count()).select_from(Goal).where(Goal.deal_id == deal.id)
    result = await db_session.execute(goal_count_stmt)
    goal_count = result.scalar()
    assert goal_count == 2
    
    token_count_stmt = select(func.count()).select_from(Token).where(Token.deal_id == deal.id)
    result = await db_session.execute(token_count_stmt)
    token_count = result.scalar()
    assert token_count == 2
    
    # Delete the deal
    await db_session.delete(deal)
    await db_session.commit()
    
    # Verify the related goals were deleted (cascade)
    goal_count_stmt = select(func.count()).select_from(Goal).where(Goal.deal_id == deal.id)
    result = await db_session.execute(goal_count_stmt)
    goal_count = result.scalar()
    assert goal_count == 0
    
    # Verify the related tokens were deleted (cascade)
    token_count_stmt = select(func.count()).select_from(Token).where(Token.deal_id == deal.id)
    result = await db_session.execute(token_count_stmt)
    token_count = result.scalar()
    assert token_count == 0

@pytest.mark.asyncio
@pytest.mark.core
async def test_enum_storage_and_retrieval(db_session):
    """Test storing and retrieving enum values in the database."""
    # Create a deal with enum values
    deal = Deal(
        title="Enum Test Deal",
        description="A deal to test enum handling",
        status=DealStatus.ACTIVE.value.lower(),  # Store lowercase enum value
        market_type=MarketType.STOCKS.value.lower(),  # Store lowercase enum value
        user_id=uuid.uuid4(),
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    
    # Verify the enum values were stored correctly
    assert deal.status == DealStatus.ACTIVE.value.lower()
    assert deal.market_type == MarketType.STOCKS.value.lower()
    
    # Query the deal and verify enum values
    stmt = select(Deal).where(Deal.id == deal.id)
    result = await db_session.execute(stmt)
    loaded_deal = result.scalar_one()
    
    assert loaded_deal.status == DealStatus.ACTIVE.value.lower()
    assert loaded_deal.market_type == MarketType.STOCKS.value.lower()
    
    # Test filtering by enum value
    stmt = select(Deal).where(Deal.status == DealStatus.ACTIVE.value.lower())
    result = await db_session.execute(stmt)
    active_deals = result.scalars().all()
    
    assert len(active_deals) >= 1
    assert any(d.id == deal.id for d in active_deals)
    
    stmt = select(Deal).where(Deal.market_type == MarketType.STOCKS.value.lower())
    result = await db_session.execute(stmt)
    stock_deals = result.scalars().all()
    
    assert len(stock_deals) >= 1
    assert any(d.id == deal.id for d in stock_deals)

@pytest.mark.asyncio
@pytest.mark.core
async def test_jsonb_operations(db_session):
    """Test JSONB operations in PostgreSQL."""
    # Create a deal with JSONB metadata
    deal = Deal(
        title="JSONB Test Deal",
        description="A deal to test JSONB operations",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=uuid.uuid4(),
        metadata={
            "priority": "high",
            "tags": ["important", "urgent", "crypto"],
            "details": {
                "target_price": 50000,
                "currency": "USD",
                "expiration": "2023-12-31"
            }
        }
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    
    # Verify the JSONB data was stored correctly
    assert deal.metadata["priority"] == "high"
    assert "important" in deal.metadata["tags"]
    assert deal.metadata["details"]["target_price"] == 50000
    
    # Update JSONB data
    deal.metadata["priority"] = "medium"
    deal.metadata["tags"].append("revised")
    deal.metadata["details"]["target_price"] = 45000
    
    await db_session.commit()
    await db_session.refresh(deal)
    
    # Verify the JSONB data was updated
    assert deal.metadata["priority"] == "medium"
    assert "revised" in deal.metadata["tags"]
    assert deal.metadata["details"]["target_price"] == 45000
    
    # Test querying with JSONB operators
    # Note: This test assumes PostgreSQL-specific JSONB operators are available
    # The exact SQL may need to be adjusted based on your SQLAlchemy setup
    
    # For this test, we'll use a more generic approach that should work
    # with most SQLAlchemy setups
    stmt = select(Deal).where(Deal.id == deal.id)
    result = await db_session.execute(stmt)
    loaded_deal = result.scalar_one()
    
    assert loaded_deal.metadata["priority"] == "medium"
    assert "revised" in loaded_deal.metadata["tags"]
    assert loaded_deal.metadata["details"]["target_price"] == 45000

@pytest.mark.asyncio
@pytest.mark.core
async def test_transaction_rollback(db_session):
    """Test transaction rollback behavior."""
    # Create a user
    user = User(
        email="rollback@example.com",
        username="rollbackuser",
        full_name="Rollback Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Start a transaction
    # Create a deal
    deal = Deal(
        title="Transaction Test Deal",
        description="A deal to test transactions",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id
    )
    db_session.add(deal)
    
    # Create a goal
    goal = Goal(
        title="Transaction Test Goal",
        description="A goal to test transactions",
        status=GoalStatus.PENDING.value.lower(),
        # Intentionally omit deal_id to cause an error
        user_id=user.id
    )
    db_session.add(goal)
    
    # The transaction should fail due to the missing deal_id
    with pytest.raises(IntegrityError):
        await db_session.commit()
    
    # Rollback the transaction
    await db_session.rollback()
    
    # Verify the deal was not created
    stmt = select(Deal).where(Deal.title == "Transaction Test Deal")
    result = await db_session.execute(stmt)
    deals = result.scalars().all()
    assert len(deals) == 0 

import pytest
import uuid
import datetime
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from core.models.base import Base
from core.models.user import User
from core.models.deal import Deal
from core.models.market import Market
from core.models.token import Token
from core.models.goal import Goal
from core.models.enums import DealStatus, MarketType, TokenStatus, GoalStatus

@pytest.mark.asyncio
@pytest.mark.core
async def test_user_creation(db_session):
    """Test creating a user in the database."""
    # Create a new user
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password="hashed_password_value",
        is_active=True,
        is_superuser=False
    )
    
    # Add to session and commit
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Verify the user was created with an ID
    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.email == "test@example.com"
    assert user.username == "testuser"
    assert user.full_name == "Test User"
    assert user.is_active is True
    assert user.is_superuser is False
    
    # Verify created_at and updated_at were set
    assert user.created_at is not None
    assert user.updated_at is not None
    assert isinstance(user.created_at, datetime.datetime)
    assert isinstance(user.updated_at, datetime.datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_user_unique_constraints(db_session):
    """Test unique constraints on the user model."""
    # Create a user
    user1 = User(
        email="unique@example.com",
        username="uniqueuser",
        full_name="Unique User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user1)
    await db_session.commit()
    
    # Try to create another user with the same email
    user2 = User(
        email="unique@example.com",  # Same email
        username="differentuser",
        full_name="Different User",
        hashed_password="different_hashed_password",
        is_active=True
    )
    db_session.add(user2)
    
    # Should raise an integrity error due to unique constraint
    with pytest.raises(IntegrityError):
        await db_session.commit()
    
    # Rollback the failed transaction
    await db_session.rollback()
    
    # Try to create another user with the same username
    user3 = User(
        email="different@example.com",
        username="uniqueuser",  # Same username
        full_name="Another User",
        hashed_password="another_hashed_password",
        is_active=True
    )
    db_session.add(user3)
    
    # Should raise an integrity error due to unique constraint
    with pytest.raises(IntegrityError):
        await db_session.commit()
    
    # Rollback the failed transaction
    await db_session.rollback()

@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_creation_and_relationships(db_session):
    """Test creating a deal with relationships to other models."""
    # Create a user
    user = User(
        email="deal_test@example.com",
        username="dealuser",
        full_name="Deal Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a market
    market = Market(
        name="Test Market",
        description="A test market for deal relationships",
        type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a deal linked to the user and market
    deal = Deal(
        title="Test Deal",
        description="A test deal with relationships",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        market_id=market.id,
        metadata={"priority": "high"}
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    
    # Create goals for the deal
    goal1 = Goal(
        title="Goal 1",
        description="First test goal",
        status=GoalStatus.PENDING.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        priority=1
    )
    
    goal2 = Goal(
        title="Goal 2",
        description="Second test goal",
        status=GoalStatus.PENDING.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        priority=2
    )
    
    db_session.add_all([goal1, goal2])
    await db_session.commit()
    
    # Create tokens for the deal
    token1 = Token(
        name="Token 1",
        symbol="TK1",
        status=TokenStatus.ACTIVE.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        metadata={"decimals": 18}
    )
    
    token2 = Token(
        name="Token 2",
        symbol="TK2",
        status=TokenStatus.ACTIVE.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        metadata={"decimals": 6}
    )
    
    db_session.add_all([token1, token2])
    await db_session.commit()
    
    # Refresh the deal to load relationships
    await db_session.refresh(deal)
    
    # Test relationship loading via query
    stmt = select(Deal).where(Deal.id == deal.id)
    result = await db_session.execute(stmt)
    loaded_deal = result.scalar_one()
    
    # Verify the deal was created with relationships
    assert loaded_deal.id == deal.id
    assert loaded_deal.user_id == user.id
    assert loaded_deal.market_id == market.id
    
    # Load and verify goals relationship
    stmt = select(Goal).where(Goal.deal_id == deal.id).order_by(Goal.priority)
    result = await db_session.execute(stmt)
    goals = result.scalars().all()
    
    assert len(goals) == 2
    assert goals[0].title == "Goal 1"
    assert goals[1].title == "Goal 2"
    
    # Load and verify tokens relationship
    stmt = select(Token).where(Token.deal_id == deal.id).order_by(Token.symbol)
    result = await db_session.execute(stmt)
    tokens = result.scalars().all()
    
    assert len(tokens) == 2
    assert tokens[0].symbol == "TK1"
    assert tokens[1].symbol == "TK2"

@pytest.mark.asyncio
@pytest.mark.core
async def test_cascade_delete(db_session):
    """Test cascade delete behavior for related models."""
    # Create a user
    user = User(
        email="cascade@example.com",
        username="cascadeuser",
        full_name="Cascade Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Cascade Test Deal",
        description="A deal to test cascade delete",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create goals for the deal
    goal1 = Goal(
        title="Cascade Goal 1",
        description="First cascade test goal",
        status=GoalStatus.PENDING.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        priority=1
    )
    
    goal2 = Goal(
        title="Cascade Goal 2",
        description="Second cascade test goal",
        status=GoalStatus.PENDING.value.lower(),
        deal_id=deal.id,
        user_id=user.id,
        priority=2
    )
    
    db_session.add_all([goal1, goal2])
    await db_session.commit()
    
    # Create tokens for the deal
    token1 = Token(
        name="Cascade Token 1",
        symbol="CTK1",
        status=TokenStatus.ACTIVE.value.lower(),
        deal_id=deal.id,
        user_id=user.id
    )
    
    token2 = Token(
        name="Cascade Token 2",
        symbol="CTK2",
        status=TokenStatus.ACTIVE.value.lower(),
        deal_id=deal.id,
        user_id=user.id
    )
    
    db_session.add_all([token1, token2])
    await db_session.commit()
    
    # Verify the related records exist
    goal_count_stmt = select(func.count()).select_from(Goal).where(Goal.deal_id == deal.id)
    result = await db_session.execute(goal_count_stmt)
    goal_count = result.scalar()
    assert goal_count == 2
    
    token_count_stmt = select(func.count()).select_from(Token).where(Token.deal_id == deal.id)
    result = await db_session.execute(token_count_stmt)
    token_count = result.scalar()
    assert token_count == 2
    
    # Delete the deal
    await db_session.delete(deal)
    await db_session.commit()
    
    # Verify the related goals were deleted (cascade)
    goal_count_stmt = select(func.count()).select_from(Goal).where(Goal.deal_id == deal.id)
    result = await db_session.execute(goal_count_stmt)
    goal_count = result.scalar()
    assert goal_count == 0
    
    # Verify the related tokens were deleted (cascade)
    token_count_stmt = select(func.count()).select_from(Token).where(Token.deal_id == deal.id)
    result = await db_session.execute(token_count_stmt)
    token_count = result.scalar()
    assert token_count == 0

@pytest.mark.asyncio
@pytest.mark.core
async def test_enum_storage_and_retrieval(db_session):
    """Test storing and retrieving enum values in the database."""
    # Create a deal with enum values
    deal = Deal(
        title="Enum Test Deal",
        description="A deal to test enum handling",
        status=DealStatus.ACTIVE.value.lower(),  # Store lowercase enum value
        market_type=MarketType.STOCKS.value.lower(),  # Store lowercase enum value
        user_id=uuid.uuid4(),
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    
    # Verify the enum values were stored correctly
    assert deal.status == DealStatus.ACTIVE.value.lower()
    assert deal.market_type == MarketType.STOCKS.value.lower()
    
    # Query the deal and verify enum values
    stmt = select(Deal).where(Deal.id == deal.id)
    result = await db_session.execute(stmt)
    loaded_deal = result.scalar_one()
    
    assert loaded_deal.status == DealStatus.ACTIVE.value.lower()
    assert loaded_deal.market_type == MarketType.STOCKS.value.lower()
    
    # Test filtering by enum value
    stmt = select(Deal).where(Deal.status == DealStatus.ACTIVE.value.lower())
    result = await db_session.execute(stmt)
    active_deals = result.scalars().all()
    
    assert len(active_deals) >= 1
    assert any(d.id == deal.id for d in active_deals)
    
    stmt = select(Deal).where(Deal.market_type == MarketType.STOCKS.value.lower())
    result = await db_session.execute(stmt)
    stock_deals = result.scalars().all()
    
    assert len(stock_deals) >= 1
    assert any(d.id == deal.id for d in stock_deals)

@pytest.mark.asyncio
@pytest.mark.core
async def test_jsonb_operations(db_session):
    """Test JSONB operations in PostgreSQL."""
    # Create a deal with JSONB metadata
    deal = Deal(
        title="JSONB Test Deal",
        description="A deal to test JSONB operations",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=uuid.uuid4(),
        metadata={
            "priority": "high",
            "tags": ["important", "urgent", "crypto"],
            "details": {
                "target_price": 50000,
                "currency": "USD",
                "expiration": "2023-12-31"
            }
        }
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    
    # Verify the JSONB data was stored correctly
    assert deal.metadata["priority"] == "high"
    assert "important" in deal.metadata["tags"]
    assert deal.metadata["details"]["target_price"] == 50000
    
    # Update JSONB data
    deal.metadata["priority"] = "medium"
    deal.metadata["tags"].append("revised")
    deal.metadata["details"]["target_price"] = 45000
    
    await db_session.commit()
    await db_session.refresh(deal)
    
    # Verify the JSONB data was updated
    assert deal.metadata["priority"] == "medium"
    assert "revised" in deal.metadata["tags"]
    assert deal.metadata["details"]["target_price"] == 45000
    
    # Test querying with JSONB operators
    # Note: This test assumes PostgreSQL-specific JSONB operators are available
    # The exact SQL may need to be adjusted based on your SQLAlchemy setup
    
    # For this test, we'll use a more generic approach that should work
    # with most SQLAlchemy setups
    stmt = select(Deal).where(Deal.id == deal.id)
    result = await db_session.execute(stmt)
    loaded_deal = result.scalar_one()
    
    assert loaded_deal.metadata["priority"] == "medium"
    assert "revised" in loaded_deal.metadata["tags"]
    assert loaded_deal.metadata["details"]["target_price"] == 45000

@pytest.mark.asyncio
@pytest.mark.core
async def test_transaction_rollback(db_session):
    """Test transaction rollback behavior."""
    # Create a user
    user = User(
        email="rollback@example.com",
        username="rollbackuser",
        full_name="Rollback Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Start a transaction
    # Create a deal
    deal = Deal(
        title="Transaction Test Deal",
        description="A deal to test transactions",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id
    )
    db_session.add(deal)
    
    # Create a goal
    goal = Goal(
        title="Transaction Test Goal",
        description="A goal to test transactions",
        status=GoalStatus.PENDING.value.lower(),
        # Intentionally omit deal_id to cause an error
        user_id=user.id
    )
    db_session.add(goal)
    
    # The transaction should fail due to the missing deal_id
    with pytest.raises(IntegrityError):
        await db_session.commit()
    
    # Rollback the transaction
    await db_session.rollback()
    
    # Verify the deal was not created
    stmt = select(Deal).where(Deal.title == "Transaction Test Deal")
    result = await db_session.execute(stmt)
    deals = result.scalars().all()
    assert len(deals) == 0 