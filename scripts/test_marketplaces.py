#!/usr/bin/env python3
"""
Simple script to test the market integrations with Oxylabs.

This script will test the search functionality for all supported markets:
- Amazon
- Walmart
- Google Shopping

Usage:
    python test_marketplaces.py [market_name]

If no market name is provided, it will test all markets.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
import dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("market_test")

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env.development
dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.development'))

# Import necessary modules
from core.integrations.oxylabs import get_oxylabs, OxylabsService
from core.database import get_session

# Get Oxylabs credentials directly from environment
OXYLABS_USERNAME = os.environ.get("OXYLABS_USERNAME", "anton_XBAap")
OXYLABS_PASSWORD = os.environ.get("OXYLABS_PASSWORD", "q+yU5aZP3sp96iN")

# Test query
TEST_QUERY = "Logitech G604 gaming mouse"

async def test_marketplace(market_name: str, query: str = TEST_QUERY) -> Dict[str, Any]:
    """Test a specific marketplace search.
    
    Args:
        market_name: Name of the market to test (amazon, walmart, google_shopping)
        query: Search query
        
    Returns:
        Search results
    """
    logger.info(f"Testing {market_name.upper()} search with query: '{query}'")
    
    # Get Oxylabs service
    try:
        # Properly use the session async generator
        session_gen = get_session()
        db = None
        try:
            db = await session_gen.__anext__()
            # Create Oxylabs service with explicit credentials
            oxylabs_service = OxylabsService(
                username=OXYLABS_USERNAME,
                password=OXYLABS_PASSWORD,
                db=db
            )
            
            if market_name.lower() == "amazon":
                result = await oxylabs_service.search_amazon(query=query)
            elif market_name.lower() == "walmart":
                result = await oxylabs_service.search_walmart(query=query)
            elif market_name.lower() == "google_shopping":
                result = await oxylabs_service.search_google_shopping(query=query)
            else:
                logger.error(f"Unknown market: {market_name}")
                return {"error": f"Unknown market: {market_name}"}
                
            # Check the status of the result
            if isinstance(result, dict):
                status = result.get("status", "unknown")
                results_count = len(result.get("results", []))
                logger.info(f"{market_name.upper()} search returned status '{status}' with {results_count} results")
                
                # Save results to file for inspection
                output_file = f"{market_name.lower()}_search_results.json"
                with open(output_file, "w") as f:
                    json.dump(result, f, indent=2)
                logger.info(f"Results saved to {output_file}")
            
            return result
        finally:
            # Close the session
            if db is not None:
                try:
                    await session_gen.aclose()
                except Exception as e:
                    logger.error(f"Error closing db session: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error testing {market_name}: {str(e)}")
        return {"error": str(e)}

async def main():
    """Main function to run the marketplace tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test marketplace integrations")
    parser.add_argument("market", nargs="?", help="Market to test (amazon, walmart, google_shopping)")
    parser.add_argument("--query", "-q", help="Search query to use")
    args = parser.parse_args()
    
    query = args.query or TEST_QUERY
    
    if args.market:
        # Test specific market
        if args.market.lower() not in ["amazon", "walmart", "google_shopping"]:
            logger.error(f"Unknown market: {args.market}")
            logger.info("Available markets: amazon, walmart, google_shopping")
            return
            
        await test_marketplace(args.market.lower(), query)
    else:
        # Test all markets
        logger.info("Testing all marketplaces...")
        
        results = {}
        for market in ["amazon", "walmart", "google_shopping"]:
            results[market] = await test_marketplace(market, query)
            
        # Save combined results
        with open("all_market_results.json", "w") as f:
            json.dump(results, f, indent=2)
        logger.info("Combined results saved to all_market_results.json")

if __name__ == "__main__":
    asyncio.run(main()) 