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
TEST_TIMEOUT = aiohttp.ClientTimeout(
    total=120,  # 2 minutes total timeout
    connect=30,  # 30 seconds for connection
    sock_connect=30,  # 30 seconds for socket connection
    sock_read=60  # 1 minute for socket read
)  # Longer timeout for complex operations
CACHE_TTL = 300  # 5 minutes cache
TEST_PRODUCT = "laptop"  # Simple product to test with

@pytest.fixture
def redis_mock():
    """Redis mock fixture."""
    return AsyncRedisMock()

@pytest.fixture
def scraper_service(redis_mock, mock_settings):
    """ScraperAPI service fixture."""
    service = ScraperAPIService(
        api_key=mock_settings.SCRAPER_API_KEY,
        base_url="http://api.scraperapi.com",
        redis_client=redis_mock
    )
    # Override timeout for tests
    service.timeout = TEST_TIMEOUT
    return service

@pytest.fixture
def market_factory(redis_mock, mock_settings):
    """Market factory fixture."""
    return MarketIntegrationFactory(
        redis_client=redis_mock,
        api_key=mock_settings.SCRAPER_API_KEY
    )

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_basic_connectivity(scraper_service):
    """Test basic API connectivity with minimal parameters."""
    service = scraper_service
    
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
    service = scraper_service
    
    try:
        # Test search using the proper method
        products = await service.search_amazon(
            query=TEST_PRODUCT,  # Use simpler product query
            page=1,
            cache_ttl=CACHE_TTL
        )
        
        assert isinstance(products, list)
        assert len(products) > 0
        
        first_product = products[0]
        assert 'id' in first_product
        assert 'title' in first_product
        assert 'price' in first_product
        assert 'url' in first_product
        assert 'market_type' in first_product
        assert first_product['market_type'] == 'amazon'
        
        print("\nAmazon Search Results:")
        print(f"Found {len(products)} products")
        print(f"First product: {first_product['title']}")
        print(f"Price: ${first_product['price']}")
        
    except MarketIntegrationError as e:
        print(f"\nMarket integration error: {str(e)}")
        raise
    except asyncio.TimeoutError:
        print("\nRequest timed out")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_walmart_search(scraper_service):
    """Test Walmart product search."""
    service = scraper_service
    
    try:
        # Test search using the proper method
        products = await service.search_walmart_products(
            query=TEST_PRODUCT,  # Use simpler product query
            page=1,
            cache_ttl=CACHE_TTL
        )
        
        assert isinstance(products, list)
        assert len(products) > 0
        
        first_product = products[0]
        assert 'id' in first_product
        assert 'title' in first_product
        assert 'price' in first_product
        assert 'url' in first_product
        assert 'market_type' in first_product
        assert first_product['market_type'] == 'walmart'
        
        print("\nWalmart Search Results:")
        print(f"Found {len(products)} products")
        print(f"First product: {first_product['title']}")
        print(f"Price: ${first_product['price']}")
        
    except MarketIntegrationError as e:
        print(f"\nMarket integration error: {str(e)}")
        raise
    except asyncio.TimeoutError:
        print("\nRequest timed out")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_product_details(scraper_service):
    """Test product details retrieval."""
    service = scraper_service
    
    try:
        # Get Amazon product
        amazon_products = await service.search_amazon("gaming laptop", page=1)
        if amazon_products:
            product_id = amazon_products[0]['id']
            amazon_product = await service.get_amazon_product(product_id)
            
            assert amazon_product is not None
            assert isinstance(amazon_product, dict)
            print("\nAmazon Product Details:")
            print(f"ASIN: {amazon_product.get('asin')}")
            print(f"Name: {amazon_product.get('name')}")
            print(f"Price: {amazon_product.get('price_string')}")
            print(f"Rating: {amazon_product.get('stars')}")
        
        # Get Walmart product
        walmart_products = await service.search_walmart_products("gaming laptop", page=1)
        if walmart_products:
            product_id = walmart_products[0]['id']
            walmart_product = await service.get_walmart_product(product_id)
            
            assert walmart_product is not None
            print("\nWalmart Product Details:")
            print(f"Title: {walmart_product.get('title')}")
            print(f"Price: ${walmart_product.get('price')}")
            print(f"Rating: {walmart_product.get('rating')}")
            
    except MarketIntegrationError as e:
        print(f"\nMarket integration error: {str(e)}")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_credit_usage(scraper_service):
    """Test credit usage tracking."""
    service = scraper_service
    
    try:
        # Make a request to generate credit usage
        await service.search_amazon(TEST_PRODUCT, page=1)
        
        # Check credit usage
        usage = await service.get_credit_usage()
        
        assert 'credits_used' in usage
        assert 'credits_remaining' in usage
        assert isinstance(usage['credits_used'], int)
        assert isinstance(usage['credits_remaining'], int)
        assert usage['credits_used'] > 0
        
        print("\nCredit Usage:")
        print(f"Credits used: {usage['credits_used']}")
        print(f"Credits remaining: {usage['credits_remaining']}")
        
    except Exception as e:
        print(f"\nError checking credit usage: {str(e)}")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_market_factory(market_factory):
    """Test MarketIntegrationFactory."""
    factory = market_factory
    
    try:
        # Test Amazon search through factory
        amazon_results = await factory.search_products("amazon", "gaming laptop")
        assert isinstance(amazon_results, list)
        assert len(amazon_results) > 0
        
        # Test Walmart search through factory
        walmart_results = await factory.search_products("walmart", "gaming laptop")
        assert isinstance(walmart_results, list)
        assert len(walmart_results) > 0
        
        print("\nMarket Factory Results:")
        print(f"Amazon products found: {len(amazon_results)}")
        print(f"Walmart products found: {len(walmart_results)}")
        
        # Validate product structure
        for product in amazon_results[:1]:
            assert isinstance(product, dict)
            assert 'asin' in product
            assert 'name' in product
            assert 'price_string' in product
            assert 'url' in product
            assert 'market_type' in product
            
        for product in walmart_results[:1]:
            assert isinstance(product, dict)
            assert 'id' in product
            assert 'title' in product
            assert 'price' in product
            assert 'url' in product
            assert 'market_type' in product
        
    except MarketIntegrationError as e:
        print(f"\nMarket integration error: {str(e)}")
        raise

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_error_handling(scraper_service, mock_settings):
    """Test error handling."""
    service = scraper_service
    
    # Test invalid product ID
    with pytest.raises(ProductNotFoundError) as exc_info:
        await service.get_amazon_product("invalid_product_id_12345")
    assert "Product invalid_product_id_12345 not found" in str(exc_info.value)
    
    # Test invalid market
    factory = MarketIntegrationFactory(
        redis_client=AsyncRedisMock(),
        api_key=mock_settings.SCRAPER_API_KEY
    )
    with pytest.raises(MarketIntegrationError) as exc_info:
        await factory.search_products("invalid_market", TEST_PRODUCT)
    assert "invalid_market" in str(exc_info.value)

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_concurrent_requests(scraper_service):
    """Test concurrent request handling."""
    service = scraper_service
    
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
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        success_count = sum(1 for r in results if isinstance(r, list))
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        print(f"\nConcurrent Requests:")
        print(f"Successful requests: {success_count} out of {len(tasks)}")
        print(f"Failed requests: {error_count}")
        
        # At least one request should succeed
        assert success_count > 0
        
        # Check the successful results
        for result in results:
            if isinstance(result, list):
                assert len(result) > 0
                first_product = result[0]
                assert 'id' in first_product
                assert 'title' in first_product
                assert 'price' in first_product
                
    except Exception as e:
        print(f"\nError in concurrent requests: {str(e)}")
        raise

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 