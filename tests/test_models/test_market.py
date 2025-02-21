"""Market model tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from core.models.market import Market
from core.models.enums import MarketType, MarketStatus
from core.exceptions import DatabaseError

@pytest.mark.asyncio
async def test_create_market(async_session: AsyncSession):
    """Test creating a market."""
    market = Market(
        name="Test Market",
        type=MarketType.AMAZON.value,
        description="Test market description",
        api_endpoint="https://api.test.com",
        api_key="test_key",
        status=MarketStatus.ACTIVE.value,
        config={"rate_limit": 100},
        rate_limit=100,
        is_active=True
    )
    
    async_session.add(market)
    await async_session.commit()
    await async_session.refresh(market)
    
    assert market.id is not None
    assert market.name == "Test Market"
    assert market.type == MarketType.AMAZON.value
    assert market.status == MarketStatus.ACTIVE.value
    assert market.config == {"rate_limit": 100}
    assert market.rate_limit == 100
    assert market.is_active is True
    assert market.error_count == 0
    assert market.requests_today == 0
    assert market.total_requests == 0
    assert market.success_rate == 1.0
    assert market.avg_response_time == 0.0
    assert market.created_at is not None
    assert market.updated_at is not None

@pytest.mark.asyncio
async def test_update_market(async_session: AsyncSession):
    """Test updating a market."""
    # Create initial market
    market = Market(
        name="Test Market",
        type=MarketType.AMAZON.value,
        status=MarketStatus.ACTIVE.value
    )
    async_session.add(market)
    await async_session.commit()
    
    # Update market
    market.name = "Updated Market"
    market.status = MarketStatus.MAINTENANCE.value
    market.error_count = 1
    await async_session.commit()
    await async_session.refresh(market)
    
    assert market.name == "Updated Market"
    assert market.status == MarketStatus.MAINTENANCE.value
    assert market.error_count == 1

@pytest.mark.asyncio
async def test_delete_market(async_session: AsyncSession):
    """Test deleting a market."""
    market = Market(
        name="Test Market",
        type=MarketType.AMAZON.value,
        status=MarketStatus.ACTIVE.value
    )
    async_session.add(market)
    await async_session.commit()
    
    market_id = market.id
    await async_session.delete(market)
    await async_session.commit()
    
    # Try to fetch deleted market
    deleted_market = await async_session.get(Market, market_id)
    assert deleted_market is None

@pytest.mark.asyncio
async def test_market_unique_name(async_session: AsyncSession):
    """Test market name uniqueness constraint."""
    market1 = Market(
        name="Test Market",
        type=MarketType.AMAZON.value,
        status=MarketStatus.ACTIVE.value
    )
    async_session.add(market1)
    await async_session.commit()
    
    # Try to create another market with the same name
    market2 = Market(
        name="Test Market",
        type=MarketType.WALMART.value,
        status=MarketStatus.ACTIVE.value
    )
    async_session.add(market2)
    
    with pytest.raises(IntegrityError):
        await async_session.commit()
    await async_session.rollback()

@pytest.mark.asyncio
async def test_market_status_transition(async_session: AsyncSession):
    """Test market status transitions."""
    market = Market(
        name="Test Market",
        type=MarketType.AMAZON.value,
        status=MarketStatus.ACTIVE.value
    )
    async_session.add(market)
    await async_session.commit()
    
    # Test valid status transitions
    valid_transitions = [
        MarketStatus.MAINTENANCE.value,
        MarketStatus.RATE_LIMITED.value,
        MarketStatus.ERROR.value,
        MarketStatus.INACTIVE.value
    ]
    
    for status in valid_transitions:
        market.status = status
        await async_session.commit()
        await async_session.refresh(market)
        assert market.status == status

@pytest.mark.asyncio
async def test_market_metrics_update(async_session: AsyncSession):
    """Test updating market metrics."""
    market = Market(
        name="Test Market",
        type=MarketType.AMAZON.value,
        status=MarketStatus.ACTIVE.value,
        success_rate=1.0,
        error_count=0,
        requests_today=0,
        total_requests=0
    )
    async_session.add(market)
    await async_session.commit()
    
    # Simulate some activity
    market.error_count += 1
    market.requests_today += 10
    market.total_requests += 10
    market.success_rate = 0.9  # 9 successes out of 10 requests
    market.avg_response_time = 0.5
    
    await async_session.commit()
    await async_session.refresh(market)
    
    assert market.error_count == 1
    assert market.requests_today == 10
    assert market.total_requests == 10
    assert market.success_rate == 0.9
    assert market.avg_response_time == 0.5 