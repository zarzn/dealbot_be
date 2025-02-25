import pytest
from uuid import UUID
from sqlalchemy import select
from core.models.market import Market
from core.models.enums import MarketType, MarketStatus
from backend_tests.factories.market import MarketFactory
from backend_tests.utils.markers import core_test

pytestmark = pytest.mark.asyncio

@core_test
async def test_create_market(db_session):
    """Test creating a market."""
    market = await MarketFactory.create_async(
        db_session=db_session,
        name="Test Market",
        type=MarketType.TEST.value.lower(),
        api_endpoint="https://api.test.com",
        api_key="test_key",
        status=MarketStatus.ACTIVE.value.lower(),
        rate_limit=100
    )
    
    # Verify market was created
    assert market.id is not None
    assert isinstance(market.id, UUID)
    assert market.name == "Test Market"
    assert market.type == MarketType.TEST.value.lower()
    assert market.status == MarketStatus.ACTIVE.value.lower()
    assert market.rate_limit == 100
    
    # Verify market exists in database
    stmt = select(Market).where(Market.id == market.id)
    result = await db_session.execute(stmt)
    db_market = result.scalar_one()
    
    assert db_market.id == market.id
    assert db_market.name == "Test Market"
    assert db_market.type == MarketType.TEST.value.lower()
    assert db_market.status == MarketStatus.ACTIVE.value.lower()

@core_test
async def test_market_status_transitions(db_session):
    """Test market status transitions."""
    market = await MarketFactory.create_async(
        db_session=db_session,
        status=MarketStatus.ACTIVE.value.lower()
    )
    
    # Test valid status transitions
    valid_statuses = [status.value.lower() for status in MarketStatus]
    for status in valid_statuses:
        market.status = status
        await db_session.commit()
        await db_session.refresh(market)
        assert market.status == status
    
    # Test invalid status
    with pytest.raises(ValueError):
        market.status = "invalid_status"
        await db_session.commit()

@core_test
async def test_market_type_validation(db_session):
    """Test market type validation."""
    # Test valid market types
    valid_types = [market_type.value.lower() for market_type in MarketType]
    for market_type in valid_types:
        market = await MarketFactory.create_async(
            db_session=db_session,
            type=market_type
        )
        assert market.type == market_type
    
    # Test invalid type
    with pytest.raises(ValueError):
        await MarketFactory.create_async(
            db_session=db_session,
            type="invalid_type"
        )

@core_test
async def test_market_rate_limit_validation(db_session):
    """Test market rate limit validation."""
    # Test valid rate limit
    market = await MarketFactory.create_async(
        db_session=db_session,
        rate_limit=100
    )
    assert market.rate_limit == 100
    
    # Test zero rate limit
    with pytest.raises(ValueError):
        await MarketFactory.create_async(
            db_session=db_session,
            rate_limit=0
        )
    
    # Test negative rate limit
    with pytest.raises(ValueError):
        await MarketFactory.create_async(
            db_session=db_session,
            rate_limit=-1
        )

@core_test
async def test_market_config_validation(db_session):
    """Test market configuration validation."""
    config = {
        "headers": {
            "User-Agent": "Test Agent",
            "Authorization": "Bearer test_token"
        },
        "params": {
            "timeout": 30,
            "retries": 3
        }
    }
    
    market = await MarketFactory.create_async(
        db_session=db_session,
        config=config
    )
    
    assert market.config == config
    assert market.config["headers"]["User-Agent"] == "Test Agent"
    assert market.config["params"]["timeout"] == 30 