"""Test ScraperAPI integration."""

import pytest
import asyncio
from typing import Dict, Any
from datetime import datetime
from pydantic import SecretStr
import aiohttp

from core.integrations.scraper_api import ScraperAPIService
from core.integrations.market_factory import MarketIntegrationFactory
from core.exceptions.market_exceptions import (
    MarketIntegrationError,
    ProductNotFoundError
)
from tests.mocks.redis_mock import AsyncRedisMock

# Test timeout settings
TEST_TIMEOUT = 300  # 5 minutes total timeout

# HTTP client timeout settings
HTTP_TIMEOUT = aiohttp.ClientTimeout(
    total=120,  # 2 minutes total timeout
    connect=30,  # 30 seconds for connection
    sock_connect=30,  # 30 seconds for socket connection
    sock_read=60  # 1 minute for socket read
)  # Longer timeout for complex operations
CACHE_TTL = 300  # 5 minutes cache
TEST_PRODUCT = "laptop"  # Simple product to test with

@pytest.fixture
async def redis_mock():
    """Redis mock fixture."""
    mock = await AsyncRedisMock.create()  # Use the create class method
    await mock.auth("test-password")  # Authenticate the mock client
    return mock

@pytest.fixture
async def scraper_service(redis_mock, mock_settings):
    """ScraperAPI service fixture."""
    redis_client = await redis_mock  # Await the redis mock
    service = ScraperAPIService(
        api_key=mock_settings.SCRAPER_API_KEY,
        base_url="http://api.scraperapi.com",
        redis_client=redis_client  # Pass the awaited client
    )
    # Override timeout for tests
    service.timeout = HTTP_TIMEOUT
    return service

@pytest.fixture
async def market_factory(redis_mock, mock_settings):
    """Market factory fixture."""
    redis_client = await redis_mock  # Await the redis mock
    return MarketIntegrationFactory(
        redis_client=redis_client,  # Pass the awaited client
        api_key=mock_settings.SCRAPER_API_KEY
    )

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_basic_connectivity(scraper_service):
    """Test basic API connectivity with minimal parameters."""
    service = await scraper_service  # Await the fixture
    
    # Make a simple request with minimal parameters
    results = await service._make_request(
        target_url="http://httpbin.org/ip",
        params={
            'keep_headers': 'true',
            'premium': 'true'
        },
        cache_ttl=0
    )
    
    print("\nBasic Connectivity Test Results:")
    print(f"Response: {results}")
    
    assert results is not None
    assert 'origin' in results

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_amazon_search(scraper_service):
    """Test Amazon product search."""
    service = await scraper_service  # Await the fixture

    try:
        # Test search using the proper method
        products = await service.search_amazon(
            query=TEST_PRODUCT,  # Use simpler product query
            page=1,
            cache_ttl=CACHE_TTL
        )
        
        print("\nAmazon Search Results:")
        print(f"Found {len(products)} products")
        
        assert products is not None
        assert len(products) > 0
        assert all('title' in product for product in products)
        assert all('price' in product for product in products)
        
    except Exception as e:
        print(f"\nError in Amazon search: {str(e)}")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_walmart_search(scraper_service):
    """Test Walmart product search."""
    service = await scraper_service  # Await the fixture

    try:
        # Test search using the proper method
        products = await service.search_walmart_products(
            query=TEST_PRODUCT,  # Use simpler product query
            page=1,
            cache_ttl=CACHE_TTL
        )
        
        print("\nWalmart Search Results:")
        print(f"Found {len(products)} products")
        
        assert products is not None
        assert len(products) > 0
        assert all('title' in product for product in products)
        assert all('price' in product for product in products)
        
    except Exception as e:
        print(f"\nError in Walmart search: {str(e)}")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_product_details(scraper_service):
    """Test product details retrieval."""
    service = await scraper_service  # Await the fixture

    try:
        # Get Amazon product
        amazon_products = await service.search_amazon("gaming laptop", page=1)
        assert len(amazon_products) > 0
        
        # Get first product details
        product_id = amazon_products[0].get('asin') or amazon_products[0].get('id')
        assert product_id is not None
        
        # Get detailed product info
        product_details = await service.get_amazon_product(product_id)
        
        print("\nProduct Details:")
        print(f"Name: {product_details.get('name')}")
        print(f"Price: {product_details.get('price')}")
        
        assert product_details is not None
        assert 'name' in product_details
        assert 'price' in product_details
        assert 'product_information' in product_details
        
    except Exception as e:
        print(f"\nError in product details: {str(e)}")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_credit_usage(scraper_service):
    """Test credit usage tracking."""
    service = await scraper_service  # Await the fixture

    try:
        # Make a request to generate credit usage
        await service.search_amazon(TEST_PRODUCT, page=1)
        
        # Check credit usage
        date_key = datetime.utcnow().strftime('%Y-%m')
        credits_used = await service.redis_client.get(f'scraper_api:credits:{date_key}')
        print(f"\nCredits used: {credits_used}")
        assert credits_used is not None
        assert int(credits_used) > 0
        
    except Exception as e:
        print(f"\nError checking credit usage: {str(e)}")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_market_factory(market_factory):
    """Test MarketIntegrationFactory."""
    factory = await market_factory  # Await the fixture

    try:
        # Test Amazon search through factory
        amazon_results = await factory.search_products("amazon", "gaming laptop")
        assert amazon_results is not None
        assert len(amazon_results) > 0
        
        # Test Walmart search through factory
        walmart_results = await factory.search_products("walmart", "gaming laptop")
        assert walmart_results is not None
        assert len(walmart_results) > 0
        
    except Exception as e:
        print(f"\nError in market factory: {str(e)}")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_error_handling(scraper_service, mock_settings):
    """Test error handling."""
    service = await scraper_service  # Await the fixture

    # Test invalid product ID
    with pytest.raises(ProductNotFoundError) as exc_info:
        await service.get_amazon_product("invalid_product_id_12345")
    assert "Product invalid_product_id_12345 not found" in str(exc_info.value)

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_concurrent_requests(scraper_service):
    """Test concurrent request handling."""
    service = await scraper_service  # Await the fixture

    try:
        # Make multiple concurrent requests
        tasks = [
            service.search_amazon(
                query=TEST_PRODUCT,
                page=i,
                cache_ttl=CACHE_TTL
            )
            for i in range(1, 3)  # Reduced to 2 concurrent requests
        ]
        
        results = await asyncio.gather(*tasks)
        assert all(len(r) > 0 for r in results)
        
    except Exception as e:
        print(f"\nError in concurrent requests: {str(e)}")
        raise

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 