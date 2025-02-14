"""Test ScraperAPI integration."""

import pytest
import asyncio
from typing import Dict, Any
from datetime import datetime

from core.integrations.scraper_api import ScraperAPIService
from core.integrations.market_factory import MarketIntegrationFactory
from core.exceptions.market import (
    MarketIntegrationError,
    ProductNotFoundError
)

@pytest.mark.asyncio
async def test_amazon_search():
    """Test Amazon product search."""
    service = ScraperAPIService()
    
    # Test search
    results = await service.search_amazon_products("gaming laptop")
    
    assert isinstance(results, list)
    if results:  # If any results found
        first_product = results[0]
        assert 'title' in first_product
        assert 'price' in first_product or 'current_price' in first_product
        print("\nAmazon Search Results:")
        print(f"Found {len(results)} products")
        print(f"First product: {first_product.get('title')}")
        print(f"Price: ${first_product.get('price') or first_product.get('current_price')}")

@pytest.mark.asyncio
async def test_walmart_search():
    """Test Walmart product search."""
    service = ScraperAPIService()
    
    # Test search
    results = await service.search_walmart_products("gaming laptop")
    
    assert isinstance(results, list)
    if results:  # If any results found
        first_product = results[0]
        assert 'title' in first_product
        assert 'price' in first_product or 'current_price' in first_product
        print("\nWalmart Search Results:")
        print(f"Found {len(results)} products")
        print(f"First product: {first_product.get('title')}")
        print(f"Price: ${first_product.get('price') or first_product.get('current_price')}")

@pytest.mark.asyncio
async def test_product_details():
    """Test product details retrieval."""
    service = ScraperAPIService()
    
    # First get a product ID from search
    amazon_results = await service.search_amazon_products("gaming laptop")
    walmart_results = await service.search_walmart_products("gaming laptop")
    
    if amazon_results:
        product_id = amazon_results[0].get('asin') or amazon_results[0].get('product_id')
        if product_id:
            product = await service.get_amazon_product(product_id)
            assert product is not None
            print("\nAmazon Product Details:")
            print(f"Title: {product.get('title')}")
            print(f"Price: ${product.get('price') or product.get('current_price')}")
            print(f"Rating: {product.get('rating')}")
    
    if walmart_results:
        product_id = walmart_results[0].get('id') or walmart_results[0].get('product_id')
        if product_id:
            product = await service.get_walmart_product(product_id)
            assert product is not None
            print("\nWalmart Product Details:")
            print(f"Title: {product.get('title')}")
            print(f"Price: ${product.get('price') or product.get('current_price')}")
            print(f"Rating: {product.get('rating')}")

@pytest.mark.asyncio
async def test_credit_usage():
    """Test credit usage tracking."""
    service = ScraperAPIService()
    
    # Make some requests to generate credit usage
    await service.search_amazon_products("laptop")
    await service.search_walmart_products("laptop")
    
    # Check credit usage
    usage = await service.get_credit_usage()
    
    assert 'credits_used' in usage
    assert 'credits_remaining' in usage
    assert isinstance(usage['credits_used'], int)
    assert isinstance(usage['credits_remaining'], int)
    
    print("\nCredit Usage:")
    print(f"Credits used: {usage['credits_used']}")
    print(f"Credits remaining: {usage['credits_remaining']}")

@pytest.mark.asyncio
async def test_market_factory():
    """Test MarketIntegrationFactory."""
    factory = MarketIntegrationFactory()
    
    # Test Amazon search through factory
    amazon_results = await factory.search_products("amazon", "gaming laptop")
    assert isinstance(amazon_results, list)
    
    # Test Walmart search through factory
    walmart_results = await factory.search_products("walmart", "gaming laptop")
    assert isinstance(walmart_results, list)
    
    print("\nMarket Factory Results:")
    print(f"Amazon products found: {len(amazon_results)}")
    print(f"Walmart products found: {len(walmart_results)}")

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling."""
    service = ScraperAPIService()
    
    # Test invalid product ID
    with pytest.raises(ProductNotFoundError):
        await service.get_amazon_product("invalid_product_id_12345")
    
    # Test invalid market
    factory = MarketIntegrationFactory()
    with pytest.raises(MarketIntegrationError):
        await factory.search_products("invalid_market", "laptop")

@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test concurrent request handling."""
    service = ScraperAPIService()
    
    # Make multiple concurrent requests
    tasks = [
        service.search_amazon_products("laptop", page=i)
        for i in range(1, 4)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Check results
    success_count = sum(1 for r in results if isinstance(r, list))
    print(f"\nConcurrent Requests:")
    print(f"Successful requests: {success_count} out of {len(tasks)}")

if __name__ == "__main__":
    # Run tests
    pytest.main(["-v", __file__]) 