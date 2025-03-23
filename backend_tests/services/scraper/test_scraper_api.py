#!/usr/bin/env python3
"""
Test script to verify the ScraperAPI Google Shopping integration.
"""

import asyncio
import logging
import sys
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import aiohttp

# Configure logging with more details
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_scraper_api")

# Try loading the API key from multiple .env files in sequence
env_files = [
    '.env.development',
    '.env.production',
    'backend/.env.development',
    'backend/.env.production',
    '.env'
]

SCRAPER_API_KEY = None

# Try each env file until we find a valid API key
for env_file in env_files:
    if os.path.exists(env_file):
        logger.info(f"Loading environment from {env_file}")
        load_dotenv(env_file)
        if os.getenv('SCRAPER_API_KEY'):
            SCRAPER_API_KEY = os.getenv('SCRAPER_API_KEY')
            logger.info(f"Found SCRAPER_API_KEY in {env_file}")
            break

# If we still don't have a key, check if it's directly in environment variables
if not SCRAPER_API_KEY:
    SCRAPER_API_KEY = os.getenv('SCRAPER_API_KEY')
    if SCRAPER_API_KEY:
        logger.info("Found SCRAPER_API_KEY in environment variables")

class SimpleScraperAPIService:
    """A simple implementation of ScraperAPI service for testing purposes."""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://api.scraperapi.com'
        self.structured_api_endpoint = 'https://api.scraperapi.com/structured'
        
    async def search_google_shopping(self, search_query, results_limit=20):
        """Simple Google Shopping search implementation."""
        if not search_query or not search_query.strip():
            logger.error("Empty search query provided")
            raise ValueError("Search query cannot be empty")
            
        logger.info(f"Searching Google Shopping for: {search_query}")
        
        # Set up parameters for the API request
        params = {
            'api_key': self.api_key,
            'query': search_query,
            'country_code': 'us',
            'tld': 'com'
        }
        
        async with aiohttp.ClientSession() as session:
            url = f"{self.structured_api_endpoint}/google/shopping"
            logger.debug(f"Making request to: {url}")
            logger.debug(f"With params: {params}")
            
            try:
                async with session.get(url, params=params, timeout=30) as response:
                    logger.debug(f"Got response with status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"Response type: {type(data)}")
                        if isinstance(data, dict):
                            logger.debug(f"Response keys: {list(data.keys())}")
                            
                        # Extract shopping results
                        if isinstance(data, dict) and 'shopping_results' in data:
                            products = data.get('shopping_results', [])
                            
                            # Limit results if needed
                            if results_limit and len(products) > results_limit:
                                products = products[:results_limit]
                                
                            return products
                        else:
                            logger.warning(f"Unexpected response structure: {type(data)}")
                            return []
                    else:
                        error_text = await response.text()
                        logger.error(f"Error response ({response.status}): {error_text}")
                        return []
            except Exception as e:
                logger.error(f"Request error: {str(e)}")
                return []

async def test_google_shopping_search():
    """Test Google Shopping search with a simplified integration."""
    try:
        if not SCRAPER_API_KEY:
            logger.error("❌ ERROR: SCRAPER_API_KEY not found in any .env files or environment variables")
            return False
        
        # Print API key (partially masked)
        masked_key = f"{SCRAPER_API_KEY[:4]}...{SCRAPER_API_KEY[-4:]}" if len(SCRAPER_API_KEY) > 8 else "****"
        logger.info(f"Using ScraperAPI key: {masked_key}")
        
        # Create our simplified ScraperAPI service
        logger.info("Creating simplified ScraperAPI service...")
        service = SimpleScraperAPIService(api_key=SCRAPER_API_KEY)
        
        # Test a simple search query
        query = "headphones under $50"
        
        # Call our simplified implementation
        results = await service.search_google_shopping(search_query=query, results_limit=5)
        
        if results:
            logger.info(f"✅ SUCCESS: Found {len(results)} products")
            # Log the first result
            if len(results) > 0:
                product = results[0]
                logger.info(f"First product: {product.get('title', 'No title')} - ${product.get('price', 'No price')}")
                logger.info(f"URL: {product.get('url', 'No URL')}")
            return True
        else:
            logger.error("❌ FAILED: No products found or search failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ ERROR during test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info(f"Starting test at {datetime.now()}")
    result = asyncio.run(test_google_shopping_search())
    logger.info(f"Test completed at {datetime.now()}")
    sys.exit(0 if result else 1) 