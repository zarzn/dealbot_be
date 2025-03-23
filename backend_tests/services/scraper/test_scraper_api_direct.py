#!/usr/bin/env python3
"""
Simple direct test of ScraperAPI's Google Shopping endpoint.
This test bypasses our application code to determine if the service is accessible.
"""

import aiohttp
import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Set up a file handler to write logs to a file
log_file = "scraper_api_direct_test.log"
file_handler = logging.FileHandler(log_file, mode='w')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        file_handler
    ]
)
logger = logging.getLogger("direct_scraper_test")
logger.info(f"Logging to file: {os.path.abspath(log_file)}")

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

async def test_direct_scraper_api():
    """Make a direct request to ScraperAPI's Google Shopping endpoint."""
    if not SCRAPER_API_KEY:
        logger.error("❌ ERROR: SCRAPER_API_KEY not found in any .env files or environment variables")
        return False
    
    # Print API key (partially masked)
    masked_key = f"{SCRAPER_API_KEY[:4]}...{SCRAPER_API_KEY[-4:]}" if len(SCRAPER_API_KEY) > 8 else "****"
    logger.info(f"Using ScraperAPI key: {masked_key}")
    
    # Define endpoint and parameters
    url = "https://api.scraperapi.com/structured/google/shopping"
    params = {
        'api_key': SCRAPER_API_KEY,
        'query': "headphones under $50",
        'country_code': 'us',
        'tld': 'com'
    }
    
    logger.info(f"Making direct request to ScraperAPI Google Shopping endpoint")
    logger.info(f"URL: {url}")
    logger.info(f"Query: {params['query']}")
    
    # Create a timeout for our request (60 seconds)
    timeout = aiohttp.ClientTimeout(total=60)
    
    try:
        start_time = datetime.now()
        logger.info(f"Request started at: {start_time}")
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                logger.info(f"Response received in {duration:.2f} seconds with status: {response.status}")
                
                if response.status == 200:
                    # Get the response data
                    data = await response.json()
                    
                    # Save full response to file
                    with open("scraper_api_response.json", "w") as f:
                        json.dump(data, f, indent=2)
                    logger.info(f"Saved full response to scraper_api_response.json")
                    
                    # Check if we got valid results
                    if 'shopping_results' in data and len(data['shopping_results']) > 0:
                        products = data['shopping_results']
                        logger.info(f"✅ SUCCESS: Found {len(products)} products")
                        
                        # Log the first result
                        if len(products) > 0:
                            product = products[0]
                            logger.info(f"First product: {product.get('title', 'No title')} - {product.get('price', 'No price')}")
                            logger.info(f"URL: {product.get('link', product.get('url', 'No URL'))}")
                        return True
                    else:
                        logger.warning(f"Response was 200 OK but no shopping results found")
                        logger.info(f"Response keys: {list(data.keys())}")
                        return False
                else:
                    # Get the error message
                    error_text = await response.text()
                    logger.error(f"Error response ({response.status}): {error_text}")
                    return False
                    
    except asyncio.TimeoutError:
        logger.error(f"❌ REQUEST TIMED OUT after {timeout.total} seconds")
        return False
    except Exception as e:
        logger.error(f"❌ ERROR during direct API request: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info(f"Starting direct ScraperAPI test at {datetime.now()}")
    result = asyncio.run(test_direct_scraper_api())
    logger.info(f"Test completed at {datetime.now()}")
    
    # Print final summary message
    if result:
        print("\n✅ TEST SUCCESSFUL: ScraperAPI Google Shopping endpoint is accessible")
    else:
        print("\n❌ TEST FAILED: Could not access ScraperAPI Google Shopping endpoint")
    
    sys.exit(0 if result else 1) 