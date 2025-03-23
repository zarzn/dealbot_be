#!/usr/bin/env python3
"""
Test script to verify the ScraperAPI Google Shopping integration.
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Set up a file handler to write logs to a file
log_file = "scraper_api_test.log"
file_handler = logging.FileHandler(log_file, mode='w')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        file_handler
    ]
)
logger = logging.getLogger("test_scraper_api")
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

async def test_google_shopping_search():
    """Test Google Shopping search with the updated integration."""
    try:
        # First, test with our actual ScraperAPI service implementation
        logger.info("Testing with the ScraperAPIService implementation...")
        
        from core.integrations.scraper_api import ScraperAPIService
        
        # Create the ScraperAPI service
        if not SCRAPER_API_KEY:
            logger.error("❌ ERROR: SCRAPER_API_KEY not found in any .env files or environment variables")
            return False
            
        # Print API key (partially masked)
        masked_key = f"{SCRAPER_API_KEY[:4]}...{SCRAPER_API_KEY[-4:]}" if len(SCRAPER_API_KEY) > 8 else "****"
        logger.info(f"Using ScraperAPI key: {masked_key}")
        
        # Create ScraperAPI service
        logger.info("Creating ScraperAPI service...")
        service = ScraperAPIService(api_key=SCRAPER_API_KEY)
        
        # Test a simple search query
        query = "headphones under $50"
        logger.info(f"Searching Google Shopping for: '{query}'")
        
        # Set a timeout for the entire operation
        try:
            start_time = datetime.now()
            logger.info(f"ScraperAPIService search started at: {start_time}")
            
            results = await asyncio.wait_for(
                service.search_google_shopping(
                    search_query=query, 
                    results_limit=5
                ),
                timeout=70  # Set a timeout slightly higher than the service's internal timeout
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"ScraperAPIService search completed in {duration:.2f} seconds")
            
            if results:
                logger.info(f"✅ SUCCESS: Found {len(results)} products")
                # Log the first result
                if len(results) > 0:
                    product = results[0]
                    logger.info(f"First product: {product.get('title', 'No title')} - ${product.get('price', 'No price')}")
                    logger.info(f"URL: {product.get('url', 'No URL')}")
                
                # Save results to file for debugging
                with open("scraper_api_test_results.json", "w") as f:
                    json.dump(results, f, indent=2, default=str)
                logger.info(f"Saved results to scraper_api_test_results.json")
                
                return True
            else:
                logger.error("❌ FAILED: No products found or search failed")
                return False
        
        except asyncio.TimeoutError:
            logger.error(f"❌ Operation timed out after 70 seconds")
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
    
    # Print final summary message
    if result:
        print("\n✅ TEST SUCCESSFUL: ScraperAPI Google Shopping integration is working")
    else:
        print("\n❌ TEST FAILED: ScraperAPI Google Shopping integration is not working")
        
    sys.exit(0 if result else 1) 