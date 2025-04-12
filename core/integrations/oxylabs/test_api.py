"""Test utility for Oxylabs API integration.

This script provides a simple way to test the Oxylabs API directly,
which can help diagnose issues with the API configuration.
"""

import asyncio
import json
import logging
import argparse
import sys
import os

# Add the parent directory to the path so we can import the app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from core.integrations.oxylabs.client import get_oxylabs_client
from core.integrations.oxylabs.compatibility import get_oxylabs
from core.config import settings
from core.models.enums import MarketType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

logger = logging.getLogger(__name__)

async def test_amazon_search(query="laptop", country="us"):
    """Test Amazon search using Oxylabs API."""
    logger.info(f"Testing Amazon search for query: {query} in country: {country}")
    
    # Use the new modular client
    client = get_oxylabs_client()
    result = await client.search_amazon(query, country=country)
    
    logger.info(f"Amazon search result success: {result['success']}")
    if not result['success']:
        logger.error(f"Amazon search errors: {result['errors']}")
        return False
    
    logger.info(f"Found {len(result['results'])} Amazon products")
    if result['results'] and len(result['results']) > 0:
        logger.info(f"First product title: {result['results'][0].get('title', 'No title')}")
        logger.info(f"First product price: {result['results'][0].get('price', 'No price')}")
    
    return True

async def test_walmart_search(query="laptop"):
    """Test Walmart search using Oxylabs API."""
    logger.info(f"Testing Walmart search for query: {query}")
    
    # Use the new modular client
    client = get_oxylabs_client()
    result = await client.search_walmart(query)
    
    logger.info(f"Walmart search result success: {result['success']}")
    if not result['success']:
        logger.error(f"Walmart search errors: {result['errors']}")
        # Detailed error info for debugging
        errors = result.get('errors', [])
        if errors:
            for i, error in enumerate(errors):
                logger.error(f"Error {i+1}: {error}")
        return False
    
    logger.info(f"Found {len(result['results'])} Walmart products")
    if result['results'] and len(result['results']) > 0:
        logger.info(f"First product title: {result['results'][0].get('title', 'No title')}")
        logger.info(f"First product price: {result['results'][0].get('price', 'No price')}")
    
    return True

async def test_google_shopping_search(query="laptop"):
    """Test Google Shopping search using Oxylabs API."""
    logger.info(f"Testing Google Shopping search for query: {query}")
    
    # Use the new modular client
    client = get_oxylabs_client()
    result = await client.search_google_shopping(query)
    
    logger.info(f"Google Shopping search result success: {result['success']}")
    if not result['success']:
        logger.error(f"Google Shopping search errors: {result['errors']}")
        return False
    
    logger.info(f"Found {len(result['results'])} Google Shopping products")
    return True

async def test_compatibility_layer(query="laptop", market="amazon"):
    """Test the compatibility layer that mimics the old oxylabs.py implementation."""
    logger.info(f"Testing compatibility layer for {market} with query: {query}")
    
    # Use the compatibility layer
    oxylabs = await get_oxylabs()
    
    if market.lower() == "amazon":
        result = await oxylabs.search_amazon(query)
    elif market.lower() == "walmart":
        result = await oxylabs.search_walmart(query)
    elif market.lower() == "google_shopping":
        result = await oxylabs.search_google_shopping(query)
    else:
        logger.error(f"Unsupported market: {market}")
        return False
    
    logger.info(f"{market.capitalize()} search result success: {result['success']}")
    if not result['success']:
        logger.error(f"{market.capitalize()} search errors: {result['errors']}")
        return False
    
    logger.info(f"Found {len(result['results'])} {market.capitalize()} products")
    return True

async def main():
    """Run the Oxylabs API tests."""
    parser = argparse.ArgumentParser(description="Test Oxylabs API integration")
    parser.add_argument("--market", choices=["amazon", "walmart", "google_shopping", "all"], 
                        default="all", help="Market to test")
    parser.add_argument("--query", default="laptop", help="Search query")
    parser.add_argument("--country", default="us", help="Country code for Amazon search")
    parser.add_argument("--compatibility", action="store_true", 
                        help="Test the compatibility layer instead of the direct client")
    args = parser.parse_args()
    
    # Log environment setup
    logger.info(f"Testing with Oxylabs username: {bool(settings.OXYLABS_USERNAME)}")
    logger.info(f"Testing with Oxylabs password: {bool(settings.OXYLABS_PASSWORD)}")
    
    # Run the requested tests
    if args.compatibility:
        if args.market == "all" or args.market == "amazon":
            await test_compatibility_layer(args.query, "amazon")
        if args.market == "all" or args.market == "walmart":
            await test_compatibility_layer(args.query, "walmart")
        if args.market == "all" or args.market == "google_shopping":
            await test_compatibility_layer(args.query, "google_shopping")
    else:
        if args.market == "all" or args.market == "amazon":
            await test_amazon_search(args.query, args.country)
        if args.market == "all" or args.market == "walmart":
            await test_walmart_search(args.query)
        if args.market == "all" or args.market == "google_shopping":
            await test_google_shopping_search(args.query)
    
    logger.info("Tests completed")

if __name__ == "__main__":
    asyncio.run(main()) 