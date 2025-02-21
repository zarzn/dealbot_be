"""Tests for market search functionality."""

# Standard library imports
import pytest
from unittest.mock import patch, AsyncMock
from typing import Dict, Any, List
from datetime import datetime
from uuid import uuid4, UUID

# Core imports
from core.services.market_search import MarketSearchService, SearchResult
from core.agents.config.agent_config import PriorityLevel, LLMProvider
from core.models.enums import MarketType, MarketStatus
from core.models.deal import Deal, DealStatus
from core.repositories.market import MarketRepository
from core.models.market import Market

# Test imports
from tests.mocks.redis_mock import AsyncRedisMock

@pytest.fixture
def mock_product_data():
    """Mock product data."""
    return {
        "title": "ASUS ROG Gaming Laptop",
        "description": "ASUS ROG Gaming Laptop with RTX 3070, 16GB RAM",
        "url": "https://example.com/product/123",
        "price": 1299.99,
        "original_price": 1599.99,
        "currency": "USD",
        "source": "amazon",
        "image_url": "https://example.com/images/123.jpg",
        "category": "laptops",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "market_id": "00000000-0000-0000-0000-000000000001",
        "goal_id": "00000000-0000-0000-0000-000000000002",
        "seller_info": {
            "name": "ASUS Store",
            "rating": 4.5,
            "review_count": 256
        },
        "availability": {
            "in_stock": True,
            "quantity": 10
        },
        "deal_metadata": {
            "brand": "ASUS",
            "model": "ROG",
            "specs": {
                "gpu": "RTX 3070",
                "ram": "16GB",
                "storage": "1TB SSD"
            }
        },
        "status": "active"
    }

@pytest.fixture
def market_service(async_session):
    """Fixture for market search service."""
    market_repository = MarketRepository(async_session)
    return MarketSearchService(market_repository=market_repository)

@pytest.mark.asyncio
async def test_product_search(market_service, mock_product_data):
    """Test product search functionality."""
    # Create a test market instance
    test_market = Market(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Test Amazon",
        type=MarketType.AMAZON,
        description="Test market description",
        api_endpoint="https://api.test.com",
        api_key="test_key",
        status=MarketStatus.ACTIVE
    )

    # Mock market repository response
    market_service.market_repository.get_active_markets = AsyncMock(return_value=[test_market])
    
    # Mock market integration response
    mock_integration = AsyncMock()
    mock_integration.search_products = AsyncMock(
        return_value={
            "products": [mock_product_data],
            "total_found": 1
        }
    )
    
    with patch('core.integrations.factory.MarketIntegrationFactory.get_integration', return_value=mock_integration):
        result = await market_service.search_products(
            query="gaming laptop RTX 3070",
            market_types=[MarketType.AMAZON],
            max_price=1500
        )
        
        assert isinstance(result, SearchResult)
        assert len(result.products) == 1
        assert result.total_found == 1
        assert MarketType.AMAZON.value in result.successful_markets
        assert not result.failed_markets
        assert result.search_time > 0
        assert not result.cache_hit

@pytest.mark.asyncio
async def test_product_details(market_service, mock_product_data):
    """Test product details retrieval."""
    # Create a test market instance
    test_market = Market(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Amazon US",
        type=MarketType.AMAZON,
        api_endpoint="https://api.amazon.com",
        api_key="test_key",
        status=MarketStatus.ACTIVE,
        is_active=True,
        rate_limit=100
    )

    # Mock market repository response
    market_service.market_repository.get_by_type = AsyncMock(return_value=test_market)
    
    # Mock market integration response
    mock_integration = AsyncMock()
    mock_integration.get_product_details = AsyncMock(
        return_value=mock_product_data
    )
    
    with patch('core.integrations.factory.MarketIntegrationFactory.get_integration', return_value=mock_integration):
        result = await market_service.get_product_details(
            product_id="test_123",
            market_type=MarketType.AMAZON
        )
        
        assert result["title"] == mock_product_data["title"]
        assert result["price"] == mock_product_data["price"]
        assert result["deal_metadata"]["specs"]["gpu"] == "RTX 3070"

@pytest.mark.asyncio
async def test_price_history(market_service, mock_product_data):
    """Test price history retrieval."""
    # Create a test market instance
    test_market = Market(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Amazon US",
        type=MarketType.AMAZON,
        api_endpoint="https://api.amazon.com",
        api_key="test_key",
        status=MarketStatus.ACTIVE,
        is_active=True,
        rate_limit=100
    )

    # Mock market repository response
    market_service.market_repository.get_by_type = AsyncMock(return_value=test_market)
    
    # Mock market integration response
    mock_integration = AsyncMock()
    mock_integration.get_product_price_history = AsyncMock(
        return_value=[
            {
                "timestamp": datetime.utcnow(),
                "price": 1299.99,
                "currency": "USD"
            }
        ]
    )
    
    with patch('core.integrations.factory.MarketIntegrationFactory.get_integration', return_value=mock_integration):
        result = await market_service.get_product_price_history(
            product_id="test_123",
            market_type=MarketType.AMAZON,
            days=30
        )
        
        assert len(result) == 1
        assert result[0]["price"] == 1299.99
        assert "timestamp" in result[0]
        assert result[0]["currency"] == "USD"