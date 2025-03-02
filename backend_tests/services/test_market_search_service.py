"""Tests for Market Search Service.

This module contains tests for the MarketSearchService class, which provides
functionality for searching markets, retrieving product details, and price tracking.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal

from core.services.market_search import MarketSearchService, _extract_market_type, _extract_product_id
from core.models.enums import MarketType
from core.exceptions import (
    MarketError,
    ValidationError,
    IntegrationError,
    NetworkError,
    ServiceError,
    DataQualityError,
    RateLimitError
)
from utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def mock_market_repository():
    """Create a mock market repository."""
    mock_repo = AsyncMock()
    # Mock the get_market method
    mock_repo.get_market.return_value = MagicMock(
        id=uuid4(),
        name="Test Market",
        type=MarketType.AMAZON.value,
        api_endpoint="https://api.testmarket.com",
        api_key="test_api_key",
        rate_limit=100,
        timeout=30,
        retry_count=3,
        retry_delay=1,
        config={
            "headers": {"User-Agent": "Test Agent"}
        }
    )
    return mock_repo

@pytest.fixture
async def mock_integration_factory():
    """Create a mock market integration factory."""
    mock_integration = AsyncMock()
    mock_integration.search_products.return_value = [
        {
            "id": "PROD123",
            "title": "Test Product 1",
            "description": "This is a test product",
            "price": 99.99,
            "currency": "USD",
            "availability": True,
            "url": "https://amazon.com/dp/PROD123",
            "image_url": "https://example.com/image1.jpg",
            "rating": 4.5,
            "review_count": 100
        },
        {
            "id": "PROD456",
            "title": "Test Product 2",
            "description": "Another test product",
            "price": 149.99,
            "currency": "USD",
            "availability": True,
            "url": "https://amazon.com/dp/PROD456",
            "image_url": "https://example.com/image2.jpg",
            "rating": 4.2,
            "review_count": 75
        }
    ]
    
    mock_integration.get_product_details.return_value = {
        "id": "PROD123",
        "title": "Test Product 1",
        "description": "This is a test product with detailed information",
        "price": 99.99,
        "currency": "USD",
        "availability": True,
        "url": "https://amazon.com/dp/PROD123",
        "image_url": "https://example.com/image1.jpg",
        "rating": 4.5,
        "review_count": 100,
        "features": ["Feature 1", "Feature 2"],
        "specifications": {
            "brand": "TestBrand",
            "model": "TestModel",
            "weight": "1.5 kg"
        },
        "category": "Electronics",
        "variants": [
            {"id": "PROD123-VAR1", "name": "Red", "price": 99.99},
            {"id": "PROD123-VAR2", "name": "Blue", "price": 109.99}
        ]
    }
    
    mock_integration.get_price_history.return_value = [
        {"date": (datetime.utcnow() - timedelta(days=30)).isoformat(), "price": 119.99},
        {"date": (datetime.utcnow() - timedelta(days=20)).isoformat(), "price": 109.99},
        {"date": (datetime.utcnow() - timedelta(days=10)).isoformat(), "price": 99.99},
        {"date": datetime.utcnow().isoformat(), "price": 99.99}
    ]
    
    mock_factory = MagicMock()
    mock_factory.get_integration.return_value = mock_integration
    return mock_factory

@pytest.fixture
async def market_search_service(mock_market_repository, mock_integration_factory):
    """Create a market search service with mock dependencies."""
    with patch("core.services.market_search.MarketIntegrationFactory", return_value=mock_integration_factory):
        service = MarketSearchService(mock_market_repository)
        # Mock Redis for caching
        service._redis = AsyncMock()
        service._redis.get.return_value = None  # No cache by default
        return service

@service_test
async def test_search_products(market_search_service, mock_market_repository, mock_integration_factory):
    """Test searching for products."""
    # Setup
    query = "test product"
    market_type = MarketType.AMAZON
    
    # Execute
    results = await market_search_service.search_products(query, market_type)
    
    # Verify
    assert len(results) == 2
    assert results[0]["title"] == "Test Product 1"
    assert results[0]["price"] == 99.99
    assert results[1]["title"] == "Test Product 2"
    
    # Verify market repository was called
    mock_market_repository.get_market.assert_called_once_with(market_type=market_type.value)
    
    # Verify integration factory was used
    mock_integration = mock_integration_factory.get_integration.return_value
    mock_integration.search_products.assert_called_once_with(query)

@service_test
async def test_search_products_with_filters(market_search_service, mock_integration_factory):
    """Test searching for products with filters."""
    # Setup
    query = "test product"
    market_type = MarketType.AMAZON
    filters = {
        "min_price": 50,
        "max_price": 200,
        "category": "Electronics"
    }
    
    # Mock integration to handle filters
    mock_integration = mock_integration_factory.get_integration.return_value
    
    # Execute
    results = await market_search_service.search_products(
        query, 
        market_type,
        filters=filters
    )
    
    # Verify
    assert len(results) == 2
    
    # Verify integration was called with filters
    mock_integration.search_products.assert_called_once_with(
        query, 
        min_price=50, 
        max_price=200, 
        category="Electronics"
    )

@service_test
async def test_search_products_with_invalid_market(market_search_service, mock_market_repository):
    """Test searching with an invalid market type."""
    # Setup - make market repository return None
    mock_market_repository.get_market.return_value = None
    
    # Execute and verify
    with pytest.raises(MarketError, match="Market not found"):
        await market_search_service.search_products("test", MarketType.AMAZON)

@service_test
async def test_search_products_with_integration_error(market_search_service, mock_integration_factory):
    """Test error handling during product search."""
    # Setup - make integration raise an error
    mock_integration = mock_integration_factory.get_integration.return_value
    mock_integration.search_products.side_effect = IntegrationError("API error")
    
    # Execute and verify
    with pytest.raises(MarketError, match="Failed to search products"):
        await market_search_service.search_products("test", MarketType.AMAZON)

@service_test
async def test_get_product_details(market_search_service, mock_integration_factory):
    """Test getting product details."""
    # Setup
    product_id = "PROD123"
    market_type = MarketType.AMAZON
    
    # Execute
    result = await market_search_service.get_product_details(product_id, market_type)
    
    # Verify
    assert result["id"] == product_id
    assert result["title"] == "Test Product 1"
    assert result["price"] == 99.99
    assert len(result["features"]) == 2
    assert len(result["variants"]) == 2
    
    # Verify integration was called
    mock_integration = mock_integration_factory.get_integration.return_value
    mock_integration.get_product_details.assert_called_once_with(product_id)

@service_test
async def test_get_product_details_from_cache(market_search_service, mock_integration_factory):
    """Test getting product details from cache."""
    # Setup
    product_id = "PROD123"
    market_type = MarketType.AMAZON
    cached_data = {
        "id": "PROD123",
        "title": "Cached Product",
        "price": 99.99,
        "cached_at": datetime.utcnow().isoformat()
    }
    
    # Setup cache hit
    market_search_service._redis.get.return_value = cached_data
    
    # Execute
    result = await market_search_service.get_product_details(
        product_id, 
        market_type,
        use_cache=True
    )
    
    # Verify
    assert result["id"] == product_id
    assert result["title"] == "Cached Product"
    
    # Verify integration was not called
    mock_integration = mock_integration_factory.get_integration.return_value
    mock_integration.get_product_details.assert_not_called()

@service_test
async def test_get_price_history(market_search_service, mock_integration_factory):
    """Test getting price history."""
    # Setup
    product_id = "PROD123"
    market_type = MarketType.AMAZON
    days = 30
    
    # Execute
    history = await market_search_service.get_price_history(
        product_id, 
        market_type,
        days=days
    )
    
    # Verify
    assert len(history) == 4
    assert history[0]["price"] == 119.99
    assert history[-1]["price"] == 99.99
    
    # Verify integration was called
    mock_integration = mock_integration_factory.get_integration.return_value
    mock_integration.get_price_history.assert_called_once_with(
        product_id, 
        days=days
    )

@service_test
async def test_check_product_availability(market_search_service, mock_integration_factory):
    """Test checking product availability."""
    # Setup
    product_id = "PROD123"
    market_type = MarketType.AMAZON
    
    # Mock availability check
    mock_integration = mock_integration_factory.get_integration.return_value
    mock_integration.check_availability.return_value = True
    
    # Execute
    is_available = await market_search_service.check_availability(
        product_id, 
        market_type
    )
    
    # Verify
    assert is_available is True
    
    # Verify integration was called
    mock_integration.check_availability.assert_called_once_with(product_id)

@service_test
async def test_track_price(market_search_service, mock_market_repository):
    """Test tracking a product price."""
    # Setup
    product_id = "PROD123"
    market_type = MarketType.AMAZON
    user_id = uuid4()
    target_price = Decimal("90.00")
    
    # Mock methods used by track_price
    market_search_service._save_price_alert = AsyncMock()
    
    # Execute
    track_id = await market_search_service.track_price(
        product_id, 
        market_type,
        user_id, 
        target_price
    )
    
    # Verify
    assert track_id is not None
    
    # Verify alert was saved
    market_search_service._save_price_alert.assert_called_once()
    call_args = market_search_service._save_price_alert.call_args[0]
    assert call_args[0] == user_id
    assert call_args[1] == product_id
    assert call_args[2] == market_type.value
    assert call_args[3] == target_price

@service_test
async def test_get_current_price_from_url(mock_market_repository):
    """Test getting current price from a URL."""
    # Setup
    url = "https://amazon.com/dp/PROD123"
    
    # Patch the required functions
    with patch("core.services.market_search._extract_market_type", return_value=MarketType.AMAZON), \
         patch("core.services.market_search._extract_product_id", return_value="PROD123"), \
         patch("core.services.market_search.MarketSearchService.get_product_details", 
               new_callable=AsyncMock) as mock_get_details:
        
        # Mock product details
        mock_get_details.return_value = {"price": 99.99}
        
        # Execute
        from core.services.market_search import get_current_price
        price = await get_current_price(url)
        
        # Verify
        assert price == 99.99
        mock_get_details.assert_called_once()

@service_test
async def test_get_current_price_invalid_url():
    """Test getting price from an invalid URL."""
    # Setup
    url = "https://invalid-url.com/product"
    
    # Execute and verify
    with pytest.raises(ValidationError, match="Invalid product URL"):
        from core.services.market_search import get_current_price
        await get_current_price(url)

@service_test
def test_extract_market_type():
    """Test extracting market type from URL."""
    # Test various URLs
    assert _extract_market_type("https://amazon.com/dp/ABCDEF") == MarketType.AMAZON
    assert _extract_market_type("https://walmart.com/ip/12345") == MarketType.WALMART
    assert _extract_market_type("https://ebay.com/itm/67890") == MarketType.EBAY
    assert _extract_market_type("https://bestbuy.com/site/12345.p") == MarketType.BESTBUY
    assert _extract_market_type("https://unknown.com/product") is None

@service_test
def test_extract_product_id():
    """Test extracting product ID from URL."""
    # Test various URLs
    assert _extract_product_id("https://amazon.com/dp/ABCDEF") == "ABCDEF"
    assert _extract_product_id("https://amazon.com/gp/product/GHIJKL") == "GHIJKL"
    assert _extract_product_id("https://walmart.com/ip/12345") == "12345"
    assert _extract_product_id("https://ebay.com/itm/67890") == "67890"
    assert _extract_product_id("https://bestbuy.com/site/12345.p") == "12345"
    assert _extract_product_id("https://unknown.com/product") is None

@service_test
async def test_search_products_across_markets(market_search_service, mock_integration_factory):
    """Test searching for products across multiple markets."""
    # Setup
    query = "test product"
    
    # Mock getting multiple markets
    mock_market_integration = mock_integration_factory.get_integration.return_value
    market_search_service._get_all_active_markets = AsyncMock(return_value=[
        MagicMock(type=MarketType.AMAZON.value, name="Amazon"),
        MagicMock(type=MarketType.WALMART.value, name="Walmart"),
    ])
    
    # Execute
    results = await market_search_service.search_products_across_markets(query)
    
    # Verify
    assert len(results) > 0
    assert any(r["market"] == "Amazon" for r in results)
    assert any(r["market"] == "Walmart" for r in results)
    
    # Verify integration was called multiple times
    assert mock_market_integration.search_products.call_count == 2

@service_test
async def test_compare_prices(market_search_service, mock_integration_factory):
    """Test comparing prices across markets."""
    # Setup
    product_name = "Test Product"
    
    # Mock search across markets to return products from different markets
    market_search_service.search_products_across_markets = AsyncMock(return_value=[
        {
            "id": "PROD123",
            "title": "Test Product",
            "price": 99.99,
            "market": "Amazon",
            "url": "https://amazon.com/dp/PROD123"
        },
        {
            "id": "PROD456",
            "title": "Test Product",
            "price": 89.99,
            "market": "Walmart",
            "url": "https://walmart.com/ip/PROD456"
        },
        {
            "id": "PROD789",
            "title": "Test Product",
            "price": 109.99,
            "market": "BestBuy",
            "url": "https://bestbuy.com/site/PROD789.p"
        }
    ])
    
    # Execute
    comparison = await market_search_service.compare_prices(product_name)
    
    # Verify
    assert len(comparison) == 3
    
    # Sort by price to verify order
    sorted_comparison = sorted(comparison, key=lambda x: x["price"])
    assert sorted_comparison[0]["market"] == "Walmart"
    assert sorted_comparison[0]["price"] == 89.99
    assert sorted_comparison[1]["market"] == "Amazon"
    assert sorted_comparison[1]["price"] == 99.99
    assert sorted_comparison[2]["market"] == "BestBuy"
    assert sorted_comparison[2]["price"] == 109.99 