"""Deal model tests."""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from core.models.deal import Deal, DealStatus, DealSource
from core.models.price_tracking import PricePoint
from core.models.enums import MarketCategory, Currency, MarketType
from core.exceptions.deal_exceptions import (
    DealError,
    DealPriceError,
    DealValidationError,
    DealProcessingError,
    DealScoreError
)
import asyncio
from sqlalchemy import select
import time_machine

@pytest.mark.asyncio
async def test_create_deal(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test creating a deal."""
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        original_price=Decimal("149.99"),
        currency=Currency.USD.value,
        source=DealSource.AMAZON.value,
        category=MarketCategory.ELECTRONICS.value,
        status=DealStatus.ACTIVE,
        seller_info={
            "name": "Test Seller",
            "rating": 4.5,
            "reviews": 100,
            "verified": True
        },
        deal_metadata={
            "shipping": "Free",
            "availability": "In Stock",
            "condition": "New"
        }
    )
    
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)
    
    assert deal.id is not None
    assert deal.title == "Test Deal"
    assert deal.price == Decimal("99.99")
    assert deal.status == DealStatus.ACTIVE
    assert deal.seller_info["name"] == "Test Seller"
    assert deal.deal_metadata["shipping"] == "Free"
    assert deal.created_at is not None
    assert deal.updated_at is not None

@pytest.mark.asyncio
async def test_deal_relationships(async_session, test_user, test_goal, test_market):
    """Test deal relationships."""
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
        found_at=datetime.now(timezone.utc)
    )
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)
    await async_session.refresh(test_user)

    # Test relationships
    assert deal.user == test_user
    assert deal.goal == test_goal
    assert deal.market == test_market
    assert deal in await async_session.scalars(select(Deal).where(Deal.user_id == test_user.id))

@pytest.mark.asyncio
async def test_deal_price_validation(async_session, test_user, test_goal, test_market):
    """Test deal price validation."""
    # Test case where original_price is greater than price (should succeed)
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("199.99"),
        original_price=Decimal("299.99"),  # Greater than price
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
        found_at=datetime.now(timezone.utc)
    )
    async_session.add(deal)
    await async_session.commit()

    # Test negative price (should fail)
    with pytest.raises(IntegrityError, match="ch_positive_price"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            description="Test deal description",
            url="https://example.com/test-deal",
            price=Decimal("-10.00"),
            currency=Currency.USD,
            source=DealSource.AMAZON,
            category=MarketCategory.ELECTRONICS,
            found_at=datetime.now(timezone.utc)
        )
        async_session.add(deal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_deal_currency_validation(async_session, test_user, test_goal, test_market):
    """Test deal currency validation."""
    # Test invalid currency code
    with pytest.raises(ValueError, match="Invalid currency value"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            description="Test deal description",
            url="https://example.com/test-deal",
            price=Decimal("99.99"),
            currency="XYZ",  # Invalid currency code not in Currency enum
            source=DealSource.AMAZON,
            category=MarketCategory.ELECTRONICS,
            found_at=datetime.now(timezone.utc)
        )
        async_session.add(deal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_deal_url_validation(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal URL validation."""
    with pytest.raises(DealValidationError, match="Invalid URL format"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            description="Test deal description",
            url="not-a-valid-url",  # Invalid URL
            price=Decimal("99.99"),
            original_price=Decimal("149.99"),
            currency=Currency.USD.value,
            source=DealSource.AMAZON.value,
            category=MarketCategory.ELECTRONICS.value,
            status=DealStatus.ACTIVE
        )
        async_session.add(deal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_deal_seller_info_validation(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal seller info validation."""
    with pytest.raises(DealValidationError, match="Invalid seller info format"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            description="Test deal description",
            url="https://example.com/test-deal",
            price=Decimal("99.99"),
            original_price=Decimal("149.99"),
            currency=Currency.USD.value,
            source=DealSource.AMAZON.value,
            category=MarketCategory.ELECTRONICS.value,
            status=DealStatus.ACTIVE,
            seller_info="not-a-json-object"  # Invalid JSONB
        )
        async_session.add(deal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_deal_status_transitions(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal status transitions."""
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        original_price=Decimal("149.99"),
        currency=Currency.USD.value,
        source=DealSource.AMAZON.value,
        category=MarketCategory.ELECTRONICS.value,
        status=DealStatus.ACTIVE
    )
    
    async_session.add(deal)
    await async_session.commit()
    
    # Test valid transitions
    valid_transitions = [
        DealStatus.ACTIVE,
        DealStatus.EXPIRED,
        DealStatus.SOLD_OUT,
        DealStatus.INVALID,
        DealStatus.DELETED
    ]
    
    for status in valid_transitions:
        deal.status = status
        await async_session.commit()
        await async_session.refresh(deal)
        assert deal.status == status

@pytest.mark.asyncio
async def test_deal_timestamps(async_session, test_user, test_goal, test_market):
    """Test deal timestamps."""
    # Create deal
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS
    )
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)

    # Verify timestamps are timezone-aware
    assert deal.created_at.tzinfo is not None
    assert deal.updated_at.tzinfo is not None

    # Store initial timestamps
    initial_created_at = deal.created_at
    initial_updated_at = deal.updated_at

    # Verify initial timestamps are equal
    assert initial_created_at == initial_updated_at

    # Update the deal
    await asyncio.sleep(1)  # Ensure enough time passes for a noticeable difference
    deal.price = Decimal("89.99")
    await async_session.commit()
    await async_session.refresh(deal)

    # Verify timestamps after update
    assert deal.created_at == initial_created_at  # created_at should not change
    assert deal.updated_at > initial_updated_at  # updated_at should be later
    assert deal.created_at < deal.updated_at  # updated_at should be later than created_at

@pytest.mark.asyncio
async def test_deal_url_uniqueness(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test that deals with same URL and goal_id are unique."""
    deal1 = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal 1",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        original_price=Decimal("149.99"),
        currency=Currency.USD.value,
        source=DealSource.AMAZON.value,
        category=MarketCategory.ELECTRONICS.value,
        status=DealStatus.ACTIVE
    )
    
    async_session.add(deal1)
    await async_session.commit()
    
    # Try to create another deal with same URL and goal_id
    with pytest.raises(IntegrityError):
        deal2 = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal 2",
            description="Test deal description",
            url="https://example.com/test-deal",  # Same URL
            price=Decimal("89.99"),
            original_price=Decimal("139.99"),
            currency=Currency.USD.value,
            source=DealSource.AMAZON.value,
            category=MarketCategory.ELECTRONICS.value,
            status=DealStatus.ACTIVE
        )
        async_session.add(deal2)
        await async_session.commit()

@pytest.mark.asyncio
async def test_deal_price_history(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal price history tracking."""
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        original_price=Decimal("149.99"),
        currency=Currency.USD.value,
        source=DealSource.AMAZON.value,
        category=MarketCategory.ELECTRONICS.value,
        status=DealStatus.ACTIVE
    )
    
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)
    
    # Add price points with timezone-aware timestamps
    now = datetime.now(timezone.utc)
    await asyncio.sleep(0.1)  # Small delay to ensure timestamp difference
    
    price_points = [
        PricePoint(
            deal_id=deal.id,
            price=Decimal("99.99"),
            currency=Currency.USD.value,
            source=DealSource.AMAZON.value,
            timestamp=now
        ),
        PricePoint(
            deal_id=deal.id,
            price=Decimal("89.99"),
            currency=Currency.USD.value,
            source=DealSource.AMAZON.value,
            timestamp=now + timedelta(hours=1)
        )
    ]
    
    async_session.add_all(price_points)
    await async_session.commit()
    await async_session.refresh(deal)
    
    # Explicitly load price points
    price_points = await async_session.execute(
        select(PricePoint).where(PricePoint.deal_id == deal.id)
    )
    price_points = price_points.scalars().all()
    
    assert len(price_points) == 2
    assert price_points[0].price == Decimal("99.99")
    assert price_points[1].price == Decimal("89.99")

@pytest.mark.asyncio
async def test_deal_category_validation(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal category validation."""
    # Test with a non-existent category value
    with pytest.raises(ValueError, match="Invalid category value"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            url="https://example.com/test-deal",
            price=Decimal("99.99"),
            currency=Currency.USD.value,
            source=DealSource.API.value,
            category="nonexistent",  # Invalid category
            status=DealStatus.ACTIVE
        )

    # Test with a valid category
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        currency=Currency.USD.value,
        source=DealSource.API.value,
        category=MarketCategory.ELECTRONICS.value,  # Valid category
        status=DealStatus.ACTIVE
    )
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)
    assert deal.category == MarketCategory.ELECTRONICS.value

    # Test setting an invalid category after creation
    with pytest.raises(ValueError, match="Invalid category value"):
        deal.category = "nonexistent"

@pytest.mark.asyncio
async def test_deal_source_validation(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal source validation."""
    # Test with a non-existent source value
    with pytest.raises(ValueError, match="Invalid source value"):
        Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            url="https://example.com/test-deal",
            price=Decimal("99.99"),
            currency=Currency.USD.value,
            source="invalid_source",  # Invalid source
            category=MarketCategory.ELECTRONICS.value,
            status=DealStatus.ACTIVE
        )

    # Test with a valid source
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        currency=Currency.USD.value,
        source=DealSource.AMAZON.value,  # Valid source
        category=MarketCategory.ELECTRONICS.value,
        status=DealStatus.ACTIVE
    )
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)
    assert deal.source == DealSource.AMAZON.value

    # Test setting an invalid source after creation
    with pytest.raises(ValueError, match="Invalid source value"):
        deal.source = "invalid_source"

@pytest.mark.asyncio
async def test_deal_metadata_handling(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal metadata handling."""
    deal_metadata = {
        "shipping": "Free",
        "availability": "In Stock",
        "condition": "New",
        "features": ["Feature 1", "Feature 2"],
        "specifications": {
            "color": "Black",
            "size": "Large",
            "weight": "2.5 kg"
        }
    }
    
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        currency=Currency.USD.value,
        source=DealSource.AMAZON.value,
        category=MarketCategory.ELECTRONICS.value,
        status=DealStatus.ACTIVE,
        deal_metadata=deal_metadata
    )
    
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)
    
    assert deal.deal_metadata == deal_metadata
    assert deal.deal_metadata["shipping"] == "Free"
    assert len(deal.deal_metadata["features"]) == 2
    assert deal.deal_metadata["specifications"]["weight"] == "2.5 kg"

@pytest.mark.asyncio
async def test_deal_expiration(async_session, test_user, test_goal, test_market):
    """Test deal expiration."""
    now = datetime.now(timezone.utc)
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
        found_at=now,
        expires_at=now + timedelta(days=1)
    )
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)

    # Convert timestamps to UTC for comparison
    created_at_utc = deal.created_at.astimezone(timezone.utc)
    expires_at_utc = deal.expires_at.astimezone(timezone.utc)

    # Test expiration
    assert expires_at_utc > created_at_utc
    assert expires_at_utc > now
    assert expires_at_utc == (now + timedelta(days=1)) 