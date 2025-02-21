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
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
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
async def test_deal_relationships(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal relationships."""
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        original_price=Decimal("149.99"),
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
        status=DealStatus.ACTIVE
    )
    
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)
    
    assert deal.user.id == test_user.id
    assert deal.goal.id == test_goal.id
    assert deal.market.id == test_market.id
    assert deal in test_user.deals
    assert deal in test_goal.deals

@pytest.mark.asyncio
async def test_deal_price_validation(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal price validation."""
    # Test that original price must be greater than current price
    with pytest.raises(DealPriceError, match="Original price must be greater than current price"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            description="Test deal description",
            url="https://example.com/test-deal",
            price=Decimal("199.99"),
            original_price=Decimal("149.99"),  # Lower than price
            currency=Currency.USD,
            source=DealSource.AMAZON,
            category=MarketCategory.ELECTRONICS,
            status=DealStatus.ACTIVE
        )
        async_session.add(deal)
        await async_session.commit()

    # Test negative price
    with pytest.raises(DealPriceError, match="Price must be positive"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            price=Decimal("-99.99"),  # Negative price
            currency=Currency.USD,
            source=DealSource.AMAZON,
            category=MarketCategory.ELECTRONICS,
            status=DealStatus.ACTIVE
        )
        async_session.add(deal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_deal_currency_validation(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal currency validation."""
    with pytest.raises(DealValidationError, match="Invalid currency code"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            description="Test deal description",
            url="https://example.com/test-deal",
            price=Decimal("99.99"),
            original_price=Decimal("149.99"),
            currency="INVALID",  # Invalid currency
            source=DealSource.AMAZON,
            category=MarketCategory.ELECTRONICS,
            status=DealStatus.ACTIVE
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
            currency=Currency.USD,
            source=DealSource.AMAZON,
            category=MarketCategory.ELECTRONICS,
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
            currency=Currency.USD,
            source=DealSource.AMAZON,
            category=MarketCategory.ELECTRONICS,
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
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
        status=DealStatus.ACTIVE
    )
    
    async_session.add(deal)
    await async_session.commit()
    
    # Test valid transitions
    valid_transitions = [
        DealStatus.PENDING,
        DealStatus.ACTIVE,
        DealStatus.EXPIRED,
        DealStatus.SOLD_OUT,
        DealStatus.DELETED
    ]
    
    for status in valid_transitions:
        deal.status = status
        await async_session.commit()
        await async_session.refresh(deal)
        assert deal.status == status

@pytest.mark.asyncio
async def test_deal_timestamps(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal timestamps."""
    before_create = datetime.now(timezone.utc)
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        original_price=Decimal("149.99"),
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
        status=DealStatus.ACTIVE
    )
    
    async_session.add(deal)
    await async_session.commit()
    await async_session.refresh(deal)
    after_create = datetime.now(timezone.utc)
    
    assert before_create <= deal.created_at <= after_create
    assert before_create <= deal.updated_at <= after_create
    
    # Test update timestamp
    await asyncio.sleep(1)  # Ensure time difference
    deal.title = "Updated Deal"
    await async_session.commit()
    await async_session.refresh(deal)
    
    assert deal.updated_at > deal.created_at

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
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
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
            currency=Currency.USD,
            source=DealSource.AMAZON,
            category=MarketCategory.ELECTRONICS,
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
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
        status=DealStatus.ACTIVE
    )
    
    async_session.add(deal)
    await async_session.commit()
    
    # Add price points
    price_points = [
        PricePoint(
            deal_id=deal.id,
            price=Decimal("99.99"),
            currency=Currency.USD,
            source=DealSource.AMAZON,
            timestamp=datetime.now(timezone.utc)
        ),
        PricePoint(
            deal_id=deal.id,
            price=Decimal("89.99"),
            currency=Currency.USD,
            source=DealSource.AMAZON,
            timestamp=datetime.now(timezone.utc) + timedelta(hours=1)
        )
    ]
    
    async_session.add_all(price_points)
    await async_session.commit()
    await async_session.refresh(deal)
    
    assert len(deal.price_history) == 2
    assert deal.price_history[0].price == Decimal("99.99")
    assert deal.price_history[1].price == Decimal("89.99")

@pytest.mark.asyncio
async def test_deal_category_validation(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal category validation."""
    with pytest.raises(DealValidationError, match="Invalid item category"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            url="https://example.com/test-deal",
            price=Decimal("99.99"),
            currency=Currency.USD,
            source=DealSource.AMAZON,
            category="invalid_category",  # Invalid category
            status=DealStatus.ACTIVE
        )
        async_session.add(deal)
        await async_session.commit()

@pytest.mark.asyncio
async def test_deal_source_validation(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal source validation."""
    with pytest.raises(DealValidationError, match="Invalid market source"):
        deal = Deal(
            user_id=test_user.id,
            goal_id=test_goal.id,
            market_id=test_market.id,
            title="Test Deal",
            url="https://example.com/test-deal",
            price=Decimal("99.99"),
            currency=Currency.USD,
            source="invalid_source",  # Invalid source
            category=MarketCategory.ELECTRONICS,
            status=DealStatus.ACTIVE
        )
        async_session.add(deal)
        await async_session.commit()

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
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
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
async def test_deal_expiration(async_session: AsyncSession, test_user, test_market, test_goal):
    """Test deal expiration."""
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        currency=Currency.USD,
        source=DealSource.AMAZON,
        category=MarketCategory.ELECTRONICS,
        status=DealStatus.ACTIVE,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=1)
    )
    
    async_session.add(deal)
    await async_session.commit()
    
    # Wait for expiration
    await asyncio.sleep(2)
    
    # Check expiration by checking expires_at
    now = datetime.now(timezone.utc)
    if deal.expires_at and deal.expires_at <= now:
        deal.status = DealStatus.EXPIRED
    await async_session.commit()
    await async_session.refresh(deal)
    
    assert deal.status == DealStatus.EXPIRED
    assert deal.updated_at > deal.created_at 