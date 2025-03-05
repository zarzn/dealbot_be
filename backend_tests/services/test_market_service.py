import pytest
from core.services.market import MarketService
from core.services.redis import get_redis_service
from core.models.enums import MarketType, MarketStatus
from core.exceptions import MarketError, ValidationError
from factories.market import MarketFactory
from backend_tests.utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def market_service(db_session):
    redis_service = await get_redis_service()
    return MarketService(db_session, redis_service)

@service_test
@depends_on("core.test_models.test_market.test_create_market")
async def test_create_market(db_session, market_service):
    """Test creating a market through the service."""
    market_data = {
        "name": "Test Market",
        "type": MarketType.TEST.value,
        "api_endpoint": "https://api.test.com",
        "api_key": "test_key",
        "status": MarketStatus.ACTIVE.value,
        "rate_limit": 100,
        "timeout": 30,
        "retry_count": 3,
        "retry_delay": 1,
        "config": {
            "headers": {
                "User-Agent": "Test Agent",
                "Accept": "application/json"
            },
            "params": {
                "timeout": 30,
                "retries": 3
            }
        }
    }
    
    market = await market_service.create_market(**market_data)
    
    assert market.name == market_data["name"]
    assert market.type == market_data["type"]
    assert market.status == market_data["status"]
    assert market.rate_limit == market_data["rate_limit"]
    
    # Check that the original config elements are present in the returned config
    for key, value in market_data["config"].items():
        assert key in market.config
        assert market.config[key] == value
    
    # Check that connection config contains the expected timeout, retry_count, and retry_delay
    assert "connection" in market.config
    assert market.config["connection"]["timeout"] == market_data["timeout"]
    assert market.config["connection"]["retry_count"] == market_data["retry_count"]
    assert market.config["connection"]["retry_delay"] == market_data["retry_delay"]

@service_test
@depends_on("core.test_models.test_market.test_create_market")
async def test_get_market(db_session, market_service):
    """Test retrieving a market."""
    market = await MarketFactory.create_async(db_session=db_session)
    
    # Get market by ID
    retrieved_market = await market_service.get_market(market.id)
    assert retrieved_market.id == market.id
    
    # Test non-existent market
    with pytest.raises(MarketError):
        await market_service.get_market("non-existent-id")

@service_test
@depends_on("core.test_models.test_market.test_create_market")
async def test_update_market(db_session, market_service):
    """Test updating a market."""
    market = await MarketFactory.create_async(db_session=db_session)
    
    # Update market
    updates = {
        "name": "Updated Market",
        "status": MarketStatus.INACTIVE.value,
        "rate_limit": 200
    }
    
    updated_market = await market_service.update_market(
        market.id,
        **updates
    )
    
    assert updated_market.name == updates["name"]
    assert updated_market.status == updates["status"]
    assert updated_market.rate_limit == updates["rate_limit"]

@service_test
@depends_on("core.test_models.test_market.test_create_market")
async def test_list_markets(db_session, market_service):
    """Test listing markets with filters."""
    # Create multiple markets with explicit status
    markets = []
    for i in range(3):
        # Create market with explicit status
        market = await MarketFactory.create_async(
            db_session=db_session,
            name=f"Test Market {i}",
            type=MarketType.TEST.value,
            status=MarketStatus.ACTIVE.value,
            is_active=True
        )
        markets.append(market)
    
    # Verify all markets were created with ACTIVE status
    for market in markets:
        assert market.status == MarketStatus.ACTIVE.value
    
    # Test listing all markets
    all_markets = await market_service.list_markets()
    assert len(all_markets) >= 3
    
    # Test filtering by type
    test_markets = await market_service.list_markets(
        type=MarketType.TEST.value
    )
    assert len(test_markets) >= 3
    
    # Alternative approach for active markets - get all and filter in Python
    all_markets_list = await market_service.get_all_markets()
    active_markets = [m for m in all_markets_list if m.status == MarketStatus.ACTIVE.value]
    assert len(active_markets) >= 3

@service_test
@depends_on("core.test_models.test_market.test_create_market")
async def test_validate_market_config(db_session, market_service):
    """Test market configuration validation."""
    # Test invalid config structure
    with pytest.raises(ValidationError):
        await market_service.validate_market_config({
            "invalid_key": "value"
        })
    
    # Test missing required fields
    with pytest.raises(ValidationError):
        await market_service.validate_market_config({
            "headers": {}
        })
    
    # Test valid config
    valid_config = {
        "headers": {
            "User-Agent": "Test Agent",
            "Accept": "application/json"
        },
        "params": {
            "timeout": 30,
            "retries": 3
        }
    }
    validated_config = await market_service.validate_market_config(valid_config)
    assert validated_config == valid_config

@service_test
@depends_on("core.test_models.test_market.test_create_market")
async def test_market_integration(db_session, market_service):
    """Test market integration functionality."""
    # Create a market with required API credentials
    market = await MarketFactory.create_async(
        db_session=db_session,
        api_endpoint="https://test-api.example.com",
        api_key="test_api_key_12345"
    )
    
    # Test market connection
    is_connected = await market_service.test_market_connection(market.id)
    assert is_connected is True
    
    # Test rate limiting
    for _ in range(market.rate_limit + 1):
        response = await market_service.make_request(
            market.id,
            "test_endpoint"
        )
        if _ == market.rate_limit:
            assert response["status"] == "rate_limited"
        else:
            assert response["status"] == "success" 