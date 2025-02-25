"""Market model tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from core.models.market import Market
from core.models.enums import MarketType, MarketStatus
from core.exceptions import DatabaseError
from uuid import uuid4

@pytest.mark.asyncio
async def test_create_market(async_session: AsyncSession):
    """Test creating a market."""
    async with async_session.begin_nested() as nested:
        try:
            market = Market(
                name=f"Create Test Market {uuid4()}",
                type=MarketType.AMAZON,
                description="Test market description",
                api_endpoint="https://api.test.com",
                api_key="test_key",
                status=MarketStatus.ACTIVE,
                config={"rate_limit": 100},
                rate_limit=100,
                is_active=True
            )
            
            async_session.add(market)
            await async_session.flush()
            await async_session.refresh(market)
            
            assert market.id is not None
            assert market.name.startswith("Create Test Market")
            assert market.type == MarketType.AMAZON
            assert market.status == MarketStatus.ACTIVE
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
        finally:
            await nested.rollback()

@pytest.mark.asyncio
async def test_update_market(async_session: AsyncSession):
    """Test updating a market."""
    async with async_session.begin_nested() as nested:
        try:
            # Create initial market
            market = Market(
                name=f"Update Test Market {uuid4()}",
                type=MarketType.AMAZON,
                status=MarketStatus.ACTIVE
            )
            async_session.add(market)
            await async_session.flush()
            
            # Update market
            market.name = f"Updated Market {uuid4()}"
            market.status = MarketStatus.MAINTENANCE
            market.error_count = 1
            await async_session.flush()
            await async_session.refresh(market)
            
            assert market.name.startswith("Updated Market")
            assert market.status == MarketStatus.MAINTENANCE
            assert market.error_count == 1
        finally:
            await nested.rollback()

@pytest.mark.asyncio
async def test_delete_market(async_session: AsyncSession):
    """Test deleting a market."""
    async with async_session.begin_nested() as nested:
        try:
            market = Market(
                name=f"Delete Test Market {uuid4()}",
                type=MarketType.AMAZON,
                status=MarketStatus.ACTIVE
            )
            async_session.add(market)
            await async_session.flush()
            
            market_id = market.id
            await async_session.delete(market)
            await async_session.flush()
            
            # Try to fetch deleted market
            deleted_market = await async_session.get(Market, market_id)
            assert deleted_market is None
        finally:
            await nested.rollback()

@pytest.mark.asyncio
async def test_market_unique_name(async_session: AsyncSession):
    """Test market name uniqueness constraint."""
    async with async_session.begin_nested() as nested:
        try:
            name = f"Unique Test Market {uuid4()}"
            market1 = Market(
                name=name,
                type=MarketType.AMAZON,
                status=MarketStatus.ACTIVE
            )
            async_session.add(market1)
            await async_session.flush()
            
            # Try to create another market with the same name
            market2 = Market(
                name=name,  # Use the same name to test uniqueness
                type=MarketType.WALMART,
                status=MarketStatus.ACTIVE
            )
            async_session.add(market2)
            
            with pytest.raises(IntegrityError):
                await async_session.flush()
        finally:
            await nested.rollback()

@pytest.mark.asyncio
async def test_market_status_transition(async_session: AsyncSession):
    """Test market status transitions."""
    async with async_session.begin_nested() as nested:
        try:
            market = Market(
                name=f"Status Test Market {uuid4()}",
                type=MarketType.AMAZON,
                status=MarketStatus.ACTIVE
            )
            async_session.add(market)
            await async_session.flush()
            
            # Test valid status transitions
            valid_transitions = [
                MarketStatus.MAINTENANCE,
                MarketStatus.RATE_LIMITED,
                MarketStatus.ERROR,
                MarketStatus.INACTIVE
            ]
            
            for status in valid_transitions:
                market.status = status
                await async_session.flush()
                await async_session.refresh(market)
                assert market.status == status
        finally:
            await nested.rollback()

@pytest.mark.asyncio
async def test_market_metrics_update(async_session: AsyncSession):
    """Test updating market metrics."""
    async with async_session.begin_nested() as nested:
        try:
            market = Market(
                name=f"Metrics Test Market {uuid4()}",
                type=MarketType.AMAZON,
                status=MarketStatus.ACTIVE,
                success_rate=1.0,
                error_count=0,
                requests_today=0,
                total_requests=0
            )
            async_session.add(market)
            await async_session.flush()
            
            # Simulate some activity
            market.error_count += 1
            market.requests_today += 10
            market.total_requests += 10
            market.success_rate = 0.9  # 9 successes out of 10 requests
            market.avg_response_time = 0.5
            
            await async_session.flush()
            await async_session.refresh(market)
            
            assert market.error_count == 1
            assert market.requests_today == 10
            assert market.total_requests == 10
            assert market.success_rate == 0.9
            assert market.avg_response_time == 0.5
        finally:
            await nested.rollback() 