"""Test ScraperAPI integration."""

import pytest
import pytest_asyncio
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import SecretStr
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
import json

from core.integrations.scraper_api import ScraperAPIService
from core.integrations.market_factory import MarketIntegrationFactory
from core.exceptions.market_exceptions import (
    MarketIntegrationError,
    ProductNotFoundError
)
from tests.mocks.redis_mock import AsyncRedisMock

# Test timeout settings
TEST_TIMEOUT = 300  # 5 minutes total timeout
TEST_PRODUCT = "laptop"  # Simple product to test with
CACHE_TTL = 300  # 5 minutes cache

# Mock response data
MOCK_AMAZON_SEARCH_RESPONSE = {
    "results": [
        {
            "title": "Test Laptop",
            "price": 999.99,
            "asin": "B123456789",
            "url": "https://amazon.com/dp/B123456789",
            "image": "https://amazon.com/images/test.jpg",
            "rating": 4.5,
            "reviews": 100
        }
    ]
}

MOCK_WALMART_SEARCH_RESPONSE = {
    "results": [
        {
            "title": "Test Laptop",
            "price": 899.99,
            "id": "W123456789",
            "url": "https://walmart.com/ip/W123456789",
            "image": "https://walmart.com/images/test.jpg",
            "rating": 4.0,
            "reviews": 50
        }
    ]
}

MOCK_PRODUCT_DETAILS = {
    "name": "Test Gaming Laptop",
    "price": {
        "current_price": 1299.99,
        "current_price_string": "$1,299.99",
        "currency": "USD"
    },
    "asin": "B123456789",
    "product_information": {
        "brand": "Test Brand",
        "model": "Test Model",
        "specifications": {
            "processor": "Test CPU",
            "memory": "16GB",
            "storage": "512GB SSD"
        }
    }
}

class MockResponse:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status
        self.headers = {
            'Content-Type': 'application/json',
            'Date': 'Sun, 23 Feb 2025 18:50:50 GMT'
        }

    async def json(self):
        return self.data

    async def text(self):
        return str(self.data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class MockClientSession:
    def __init__(self, mock_responses):
        self.mock_responses = mock_responses
        self.get_calls = []

    def get(self, url, params=None, ssl=None):
        self.get_calls.append((url, params))
        response = None
        if "amazon/search" in url:
            response = MockResponse(MOCK_AMAZON_SEARCH_RESPONSE)
        elif "amazon/product" in url:
            if params and params.get('asin') == 'invalid_product_id_12345':
                response = MockResponse({"error": "Product not found"}, status=404)
            else:
                response = MockResponse(MOCK_PRODUCT_DETAILS)
        elif "walmart.com" in url or "walmart/search" in url:
            response = MockResponse(MOCK_WALMART_SEARCH_RESPONSE)
        else:
            response = MockResponse({"origin": "test-ip"})
        return response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class AsyncRedisPipelineMock:
    """Mock Redis pipeline for testing."""
    def __init__(self, redis_mock):
        self.commands = []
        self.results = []
        self.redis_mock = redis_mock

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def incrby(self, key: str, amount: int):
        """Mock incrby command."""
        self.commands.append(('incrby', key, amount))
        current = int(self.redis_mock.data.get(key, 0))
        new_value = current + amount
        self.redis_mock.data[key] = str(new_value)
        self.results.append(new_value)
        return self

    def expire(self, key: str, seconds: int):
        """Mock expire command."""
        self.commands.append(('expire', key, seconds))
        self.results.append(1)
        return self

    async def execute(self):
        """Execute the pipeline."""
        return self.results

@pytest_asyncio.fixture
async def redis_mock():
    """Redis mock fixture."""
    mock = AsyncRedisMock()
    await mock.auth("test-password")  # Authenticate mock
    yield mock
    await mock.close()

@pytest_asyncio.fixture
async def mock_session():
    """Mock aiohttp ClientSession."""
    return MockClientSession({})

@pytest_asyncio.fixture
async def scraper_service(redis_mock, mock_settings, mock_session):
    """ScraperAPI service fixture."""
    service = ScraperAPIService(
        api_key=mock_settings.SCRAPER_API_KEY,
        base_url="http://api.scraperapi.com",
        redis_client=redis_mock
    )
    service.timeout = aiohttp.ClientTimeout(total=5)
    
    # Patch aiohttp.ClientSession to use our mock
    with patch('aiohttp.ClientSession', return_value=mock_session):
        yield service

@pytest_asyncio.fixture
async def market_factory(redis_mock, mock_settings, mock_session):
    """Market factory fixture."""
    factory = MarketIntegrationFactory(
        redis_client=redis_mock,
        api_key=mock_settings.SCRAPER_API_KEY
    )
    
    # Patch aiohttp.ClientSession to use our mock
    with patch('aiohttp.ClientSession', return_value=mock_session):
        yield factory

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_basic_connectivity(scraper_service):
    """Test basic API connectivity with minimal parameters."""
    results = await scraper_service._make_request(
        target_url="http://httpbin.org/ip",
        params={
            'keep_headers': 'true',
            'premium': 'true'
        },
        cache_ttl=0
    )
    
    assert results is not None
    assert 'origin' in results

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_amazon_search(scraper_service):
    """Test Amazon product search."""
    products = await scraper_service.search_amazon(
        query=TEST_PRODUCT,
        page=1,
        cache_ttl=CACHE_TTL
    )
    
    assert products is not None
    assert len(products) > 0
    assert all('title' in product for product in products)
    assert all('price' in product for product in products)

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_walmart_search(scraper_service):
    """Test Walmart product search."""
    products = await scraper_service.search_walmart_products(
        query=TEST_PRODUCT,
        page=1,
        cache_ttl=CACHE_TTL
    )
    
    assert products is not None
    assert len(products) > 0
    assert all('title' in product for product in products)
    assert all('price' in product for product in products)

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_product_details(scraper_service):
    """Test product details retrieval."""
    product_details = await scraper_service.get_amazon_product("B123456789")
    
    assert product_details is not None
    assert 'name' in product_details
    assert 'price' in product_details
    assert 'product_information' in product_details

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_credit_usage(scraper_service):
    """Test credit usage tracking."""
    await scraper_service.search_amazon(TEST_PRODUCT, page=1)
    
    date_key = datetime.utcnow().strftime('%Y-%m')
    credits_used = await scraper_service.redis_client.get(f'scraper_api:credits:{date_key}')
    assert credits_used is not None
    assert int(credits_used) > 0

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_market_factory(market_factory):
    """Test MarketIntegrationFactory."""
    amazon_results = await market_factory.search_products("amazon", "gaming laptop")
    assert amazon_results is not None
    assert len(amazon_results) > 0
    
    walmart_results = await market_factory.search_products("walmart", "gaming laptop")
    assert walmart_results is not None
    assert len(walmart_results) > 0

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_error_handling(scraper_service):
    """Test error handling."""
    with pytest.raises(ProductNotFoundError):
        await scraper_service.get_amazon_product("invalid_product_id_12345")

@pytest.mark.asyncio
@pytest.mark.timeout(TEST_TIMEOUT)
async def test_concurrent_requests(scraper_service):
    """Test concurrent request handling."""
    tasks = [
        scraper_service.search_amazon(
            query=TEST_PRODUCT,
            page=i,
            cache_ttl=CACHE_TTL
        )
        for i in range(1, 3)
    ]
    
    results = await asyncio.gather(*tasks)
    assert all(len(r) > 0 for r in results)

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 