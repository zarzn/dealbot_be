#!/usr/bin/env python3
"""
Explore ScraperAPI capabilities for different markets and query formats.
This script tests different query structures across multiple marketplaces
to document what search parameters work most effectively.
"""

import asyncio
import logging
import sys
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import quote_plus
import re
import uuid
from pathlib import Path
from dotenv import load_dotenv
import aiohttp
from pprint import pformat

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"scraper_api_exploration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure file handler for logging
file_handler = logging.FileHandler(log_file, mode='w')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        file_handler
    ]
)
logger = logging.getLogger("scraper_api_explorer")
logger.info(f"Logging to file: {log_file.absolute()}")

# Load environment variables from various .env files
env_files = [
    '.env.development',
    '.env.production',
    'backend/.env.development',
    'backend/.env.production',
    '.env',
    '../.env'
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
    else:
        logger.error("No SCRAPER_API_KEY found! Please set it in an .env file or environment variable.")
        sys.exit(1)

# Results directory for saving test outputs
results_dir = Path("results")
results_dir.mkdir(exist_ok=True)

# Documentation file for recording successful query formats
docs_file = Path("docs/ScraperAPIQueryFormats.md")
docs_file.parent.mkdir(exist_ok=True)

class ScraperAPIExplorer:
    """Explorer for testing ScraperAPI capabilities with different marketplaces and query formats."""
    
    def __init__(self, api_key: str):
        """Initialize with API key."""
        self.api_key = api_key
        self.base_url = "https://api.scraperapi.com"
        self.structured_api_endpoint = "https://api.scraperapi.com/structured"
        
        # Session for making HTTP requests
        self.session = None
        
        # Results tracking
        self.results = {
            "amazon": [],
            "walmart": [],
            "google_shopping": []
        }
        
        # Successful query formats
        self.successful_formats = {
            "amazon": [],
            "walmart": [],
            "google_shopping": []
        }
        
        # Test cases for each marketplace
        self.test_cases = self._generate_test_cases()
    
    def _generate_test_cases(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate test cases for each marketplace."""
        # Common test cases across all marketplaces
        common_cases = [
            {"description": "Basic query", "query": "headphones"},
            {"description": "Multi-word query", "query": "wireless headphones"},
            {"description": "Brand query", "query": "sony headphones"},
            {"description": "Price constraint (under)", "query": "headphones under $50"},
            {"description": "Price constraint (range)", "query": "headphones $20-$50"},
            {"description": "Feature specific", "query": "noise cancelling headphones"},
            {"description": "Complex query", "query": "sony noise cancelling headphones under $100"}
        ]
        
        # Product-specific test cases
        product_cases = [
            {"description": "Electronics", "query": "bluetooth speaker"},
            {"description": "Home goods", "query": "coffee maker"},
            {"description": "Fashion", "query": "men's running shoes"},
            {"description": "Toys", "query": "lego star wars"}
        ]
        
        # Special format test cases
        special_cases = [
            {"description": "Quoted phrase", "query": '"wireless headphones"'},
            {"description": "Exclusion", "query": "headphones -wireless"},
            {"description": "OR condition", "query": "headphones OR earbuds"},
            {"description": "Specific model", "query": "iPhone 13 Pro Max"}
        ]
        
        # Combine test cases for each marketplace
        return {
            "amazon": common_cases + product_cases + special_cases,
            "walmart": common_cases + product_cases + special_cases,
            "google_shopping": common_cases + product_cases + special_cases
        }
    
    async def initialize(self):
        """Initialize HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def search_amazon(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Amazon for products with the given query."""
        logger.info(f"Searching Amazon for: '{query}'")
        
        # Create target URL for Amazon
        target_url = f"{self.structured_api_endpoint}/amazon/search"
        
        # Set up parameters
        params = {
            "api_key": self.api_key,
            "query": query,
            "country_code": "us"
        }
        
        # Make the request
        try:
            start_time = time.time()
            async with self.session.get(target_url, params=params, timeout=60) as response:
                duration = time.time() - start_time
                logger.info(f"Amazon search completed in {duration:.2f} seconds with status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Save raw response for analysis
                    response_file = results_dir / f"amazon_{quote_plus(query)}.json"
                    with open(response_file, "w") as f:
                        json.dump(data, f, indent=2)
                    
                    # Extract products from response
                    products = []
                    if isinstance(data, dict):
                        # Check various keys where products might be stored
                        for key in ["results", "products", "search_results", "data", "items"]:
                            if key in data and isinstance(data[key], list):
                                products = data[key]
                                logger.info(f"Found {len(products)} products in '{key}' key")
                                break
                    
                    # Log success or failure
                    if products:
                        logger.info(f"Amazon search successful: found {len(products)} products")
                        # Record successful query format
                        self.successful_formats["amazon"].append({
                            "query": query,
                            "products_found": len(products),
                            "response_time": duration
                        })
                        return products[:limit]
                    else:
                        logger.warning(f"Amazon search returned no products for: '{query}'")
                        return []
                else:
                    error_text = await response.text()
                    logger.error(f"Amazon search failed with status {response.status}: {error_text[:200]}")
                    return []
        except Exception as e:
            logger.error(f"Error in Amazon search: {e}")
            return []
    
    async def search_walmart(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Walmart for products with the given query."""
        logger.info(f"Searching Walmart for: '{query}'")
        
        # Create target URL
        # Use the browse API endpoint as it tends to be more reliable
        encoded_query = quote_plus(query)
        target_url = f"https://www.walmart.com/browse/search?q={encoded_query}"
        
        # Set up parameters
        params = {
            "api_key": self.api_key,
            "autoparse": "true",
            "render_js": "true",
            "country_code": "us",
            "keep_headers": "true",
            "session_number": "1"  # Helps with consistency
        }
        
        # Make the request
        try:
            start_time = time.time()
            async with self.session.get(target_url, params=params, timeout=60) as response:
                duration = time.time() - start_time
                logger.info(f"Walmart search completed in {duration:.2f} seconds with status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Save raw response for analysis
                    response_file = results_dir / f"walmart_{quote_plus(query)}.json"
                    with open(response_file, "w") as f:
                        json.dump(data, f, indent=2)
                    
                    # Extract products
                    products = []
                    if isinstance(data, dict):
                        # Check various keys where products might be stored
                        for key in ["items", "products", "results", "searchResult", "data"]:
                            if key in data and isinstance(data[key], list):
                                products = data[key]
                                logger.info(f"Found {len(products)} products in '{key}' key")
                                break
                            elif key in data and isinstance(data[key], dict) and "items" in data[key]:
                                # Handle nested structure
                                products = data[key]["items"]
                                logger.info(f"Found {len(products)} products in '{key}.items' key")
                                break
                    
                    # Log success or failure
                    if products:
                        logger.info(f"Walmart search successful: found {len(products)} products")
                        # Record successful query format
                        self.successful_formats["walmart"].append({
                            "query": query,
                            "products_found": len(products),
                            "response_time": duration
                        })
                        return products[:limit]
                    else:
                        logger.warning(f"Walmart search returned no products for: '{query}'")
                        return []
                else:
                    error_text = await response.text()
                    logger.error(f"Walmart search failed with status {response.status}: {error_text[:200]}")
                    return []
        except Exception as e:
            logger.error(f"Error in Walmart search: {e}")
            return []
    
    async def search_google_shopping(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Google Shopping for products with the given query."""
        logger.info(f"Searching Google Shopping for: '{query}'")
        
        # Create target URL
        target_url = f"{self.structured_api_endpoint}/google/shopping"
        
        # Set up parameters
        params = {
            "api_key": self.api_key,
            "query": query,
            "country_code": "us",
            "tld": "com"
        }
        
        # Make the request
        try:
            start_time = time.time()
            async with self.session.get(target_url, params=params, timeout=60) as response:
                duration = time.time() - start_time
                logger.info(f"Google Shopping search completed in {duration:.2f} seconds with status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Save raw response for analysis
                    response_file = results_dir / f"google_shopping_{quote_plus(query)}.json"
                    with open(response_file, "w") as f:
                        json.dump(data, f, indent=2)
                    
                    # Extract products
                    products = []
                    if isinstance(data, dict) and "shopping_results" in data:
                        products = data["shopping_results"]
                    
                    # Log success or failure
                    if products:
                        logger.info(f"Google Shopping search successful: found {len(products)} products")
                        # Record successful query format
                        self.successful_formats["google_shopping"].append({
                            "query": query,
                            "products_found": len(products),
                            "response_time": duration
                        })
                        return products[:limit]
                    else:
                        logger.warning(f"Google Shopping search returned no products for: '{query}'")
                        return []
                elif response.status == 404:
                    # For Google Shopping, a 404 often means no results
                    logger.info(f"Google Shopping returned 404 for '{query}', treating as empty results")
                    return []
                else:
                    error_text = await response.text()
                    logger.error(f"Google Shopping search failed with status {response.status}: {error_text[:200]}")
                    return []
        except Exception as e:
            logger.error(f"Error in Google Shopping search: {e}")
            return []
    
    async def filter_products(
        self, 
        products: List[Dict[str, Any]], 
        query: str, 
        min_price: Optional[float] = None, 
        max_price: Optional[float] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        Filter products based on various criteria and calculate relevance scores.
        
        Args:
            products: List of products to filter
            query: Search query
            min_price: Minimum price filter
            max_price: Maximum price filter
            
        Returns:
            Tuple of (filtered_products, scores_dict)
        """
        logger.info(f"Filtering {len(products)} products with min_price={min_price}, max_price={max_price}")
        
        # Normalize the query for matching
        normalized_query = query.lower()
        
        # Extract search terms from query
        search_terms = set(re.sub(r'[^\w\s]', ' ', normalized_query).split())
        # Remove common words
        stop_words = {'a', 'an', 'the', 'and', 'or', 'for', 'in', 'on', 'at', 'to', 'with', 'by', 'under', 'over'}
        search_terms = {term for term in search_terms if term not in stop_words}
        
        logger.info(f"Search terms: {search_terms}")
        
        # Extract price constraints from the query if not provided
        if min_price is None and max_price is None:
            # Check for price patterns like "under $50" or "$20-$30"
            price_under_match = re.search(r'under\s+\$?(\d+)', normalized_query)
            price_range_match = re.search(r'\$?(\d+)\s*-\s*\$?(\d+)', normalized_query)
            price_above_match = re.search(r'over\s+\$?(\d+)', normalized_query)
            
            if price_under_match:
                max_price = float(price_under_match.group(1))
                logger.info(f"Extracted max_price={max_price} from query")
            elif price_range_match:
                min_price = float(price_range_match.group(1))
                max_price = float(price_range_match.group(2))
                logger.info(f"Extracted price range min_price={min_price}, max_price={max_price} from query")
            elif price_above_match:
                min_price = float(price_above_match.group(1))
                logger.info(f"Extracted min_price={min_price} from query")
        
        # Filtered products and scores
        filtered_products = []
        product_scores = {}
        
        # Process each product
        for product in products:
            try:
                # Skip products with missing essential data
                if 'title' not in product or not product['title']:
                    continue
                
                # Initialize score
                score = 0.0
                score_reasons = []
                
                # Get product fields
                title = product.get('title', '').lower()
                description = product.get('description', '').lower()
                
                # Extract and normalize price
                price = None
                try:
                    # Handle different price formats
                    price_str = product.get('price', '')
                    if isinstance(price_str, (int, float)):
                        price = float(price_str)
                    elif isinstance(price_str, str) and price_str:
                        # Remove currency symbols and commas
                        clean_price = price_str.replace('$', '').replace('£', '').replace('€', '').replace(',', '').strip()
                        # Extract numeric part
                        digits = re.findall(r'[\d.]+', clean_price)
                        if digits:
                            price = float(digits[0])
                except (ValueError, TypeError):
                    # If price extraction fails, try alternative fields
                    for price_field in ['current_price', 'sale_price', 'price_amount']:
                        if price_field in product and product[price_field] is not None:
                            try:
                                price = float(product[price_field])
                                break
                            except (ValueError, TypeError):
                                continue
                
                # Skip products without valid price
                if price is None:
                    continue
                
                # Apply price filtering if specified
                if min_price is not None and price < min_price:
                    continue
                if max_price is not None and price > max_price:
                    continue
                
                # Calculate relevance score based on term matching
                title_matches = sum(1 for term in search_terms if term in title)
                desc_matches = sum(1 for term in search_terms if term in description)
                
                # Score: term matching in title (higher weight)
                if search_terms:
                    title_match_ratio = title_matches / len(search_terms)
                    score += title_match_ratio * 0.6  # Title matches are most important
                    if title_match_ratio > 0:
                        score_reasons.append(f"Title match: {title_match_ratio:.2f}")
                
                # Score: term matching in description (lower weight)
                if search_terms and description:
                    desc_match_ratio = desc_matches / len(search_terms)
                    score += desc_match_ratio * 0.2  # Description matches less important
                    if desc_match_ratio > 0:
                        score_reasons.append(f"Description match: {desc_match_ratio:.2f}")
                
                # Extract rating and review count if available
                rating = 0.0
                review_count = 0
                for rating_field in ['rating', 'average_rating', 'review_rating']:
                    if rating_field in product and product[rating_field] is not None:
                        try:
                            rating = float(product[rating_field])
                            break
                        except (ValueError, TypeError):
                            continue
                
                for count_field in ['review_count', 'reviews', 'review_num', 'reviews_count']:
                    if count_field in product and product[count_field] is not None:
                        try:
                            review_count = int(product[count_field])
                            break
                        except (ValueError, TypeError):
                            continue
                
                # Add score for high ratings with sufficient reviews
                if rating > 0 and review_count > 0:
                    rating_score = 0
                    if rating >= 4.5 and review_count >= 100:
                        rating_score = 0.15
                        score_reasons.append("Excellent rating (4.5+ with 100+ reviews)")
                    elif rating >= 4.0 and review_count >= 50:
                        rating_score = 0.1
                        score_reasons.append("Very good rating (4.0+ with 50+ reviews)")
                    elif rating >= 3.5 and review_count >= 20:
                        rating_score = 0.05
                        score_reasons.append("Good rating (3.5+ with 20+ reviews)")
                        
                    score += rating_score
                
                # Store the score and add product to filtered list
                product_id = product.get('id', str(uuid.uuid4()))
                product_scores[product_id] = score
                
                # Add relevance info to the product
                product['relevance_score'] = score
                product['relevance_reasons'] = score_reasons
                product['normalized_price'] = price
                filtered_products.append(product)
                
            except Exception as e:
                logger.error(f"Error filtering product: {e}")
                continue
        
        # Sort filtered products by score
        filtered_products.sort(key=lambda p: p.get('relevance_score', 0), reverse=True)
        
        logger.info(f"Filtered to {len(filtered_products)} products")
        if filtered_products:
            logger.info(f"Top product score: {filtered_products[0].get('relevance_score', 0)}")
        
        return filtered_products, product_scores
    
    async def run_test_case(self, market: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test case for a specific market."""
        query = test_case["query"]
        description = test_case["description"]
        
        logger.info(f"Testing {market} with {description}: '{query}'")
        
        # Select the appropriate search function
        if market == "amazon":
            products = await self.search_amazon(query)
        elif market == "walmart":
            products = await self.search_walmart(query)
        elif market == "google_shopping":
            products = await self.search_google_shopping(query)
        else:
            logger.error(f"Unknown market: {market}")
            return {"success": False, "error": f"Unknown market: {market}"}
        
        # Apply post-scraping filtering
        if products:
            filtered_products, scores = await self.filter_products(products, query)
            
            # Record the results
            result = {
                "market": market,
                "description": description,
                "query": query,
                "raw_products": len(products),
                "filtered_products": len(filtered_products),
                "success": len(filtered_products) > 0,
                "top_products": filtered_products[:3] if filtered_products else [],
                "execution_time": datetime.now().isoformat()
            }
            
            self.results[market].append(result)
            return result
        else:
            result = {
                "market": market,
                "description": description,
                "query": query,
                "raw_products": 0,
                "filtered_products": 0,
                "success": False,
                "execution_time": datetime.now().isoformat()
            }
            
            self.results[market].append(result)
            return result
    
    async def run_all_tests(self):
        """Run all test cases for all markets."""
        await self.initialize()
        
        try:
            # Run tests for each market
            for market, test_cases in self.test_cases.items():
                logger.info(f"Running {len(test_cases)} test cases for {market}...")
                
                for test_case in test_cases:
                    await self.run_test_case(market, test_case)
                    # Add a small delay between requests to avoid rate limiting
                    await asyncio.sleep(1)
            
            # Generate documentation
            self.generate_documentation()
            
            # Generate summary report
            summary = self.generate_summary()
            summary_file = results_dir / "scraper_api_summary.txt"
            with open(summary_file, "w") as f:
                f.write(summary)
                
            logger.info(f"Testing complete. Summary written to {summary_file}")
            logger.info(f"Documentation written to {docs_file}")
            
        finally:
            await self.close()
    
    def generate_documentation(self):
        """Generate documentation of successful query formats."""
        with open(docs_file, "w") as f:
            f.write("# ScraperAPI Query Format Documentation\n\n")
            f.write("This document contains successful query formats for different marketplaces using the ScraperAPI.\n\n")
            f.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for market, formats in self.successful_formats.items():
                if formats:
                    f.write(f"## {market.capitalize()}\n\n")
                    f.write("| Query | Products Found | Response Time (s) |\n")
                    f.write("|-------|---------------|-------------------|\n")
                    
                    # Sort by product count, descending
                    formats.sort(key=lambda x: x["products_found"], reverse=True)
                    
                    for fmt in formats:
                        f.write(f"| `{fmt['query']}` | {fmt['products_found']} | {fmt['response_time']:.2f} |\n")
                    
                    f.write("\n")
    
    def generate_summary(self) -> str:
        """Generate a summary of the test results."""
        summary = []
        summary.append("# ScraperAPI Test Summary\n")
        summary.append(f"Test run completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Overall statistics
        total_tests = sum(len(results) for results in self.results.values())
        successful_tests = sum(sum(1 for r in results if r["success"]) for results in self.results.values())
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        
        summary.append(f"Total tests run: {total_tests}")
        summary.append(f"Successful tests: {successful_tests} ({success_rate:.1f}%)\n")
        
        # Market-specific results
        for market, results in self.results.items():
            market_success = sum(1 for r in results if r["success"])
            market_rate = (market_success / len(results)) * 100 if results else 0
            
            summary.append(f"## {market.capitalize()}")
            summary.append(f"Tests: {len(results)}, Successful: {market_success} ({market_rate:.1f}%)\n")
            
            # Most successful query types
            if results:
                successful_results = [r for r in results if r["success"]]
                
                if successful_results:
                    # Sort by filtered product count
                    successful_results.sort(key=lambda r: r.get("filtered_products", 0), reverse=True)
                    
                    summary.append("### Top Performing Queries")
                    for i, result in enumerate(successful_results[:3]):
                        summary.append(f"{i+1}. '{result['query']}' - {result.get('filtered_products', 0)} products")
                    
                    summary.append("")
            
            # Failed queries
            failed_results = [r for r in results if not r["success"]]
            if failed_results:
                summary.append("### Failed Queries")
                for result in failed_results:
                    summary.append(f"- '{result['query']}' ({result['description']})")
                
                summary.append("")
        
        return "\n".join(summary)

async def main():
    """Main entry point."""
    logger.info(f"Starting ScraperAPI exploration at {datetime.now()}")
    
    # Print API key (partially masked)
    masked_key = f"{SCRAPER_API_KEY[:4]}...{SCRAPER_API_KEY[-4:]}" if len(SCRAPER_API_KEY) > 8 else "****"
    logger.info(f"Using ScraperAPI key: {masked_key}")
    
    # Create and run the explorer
    explorer = ScraperAPIExplorer(api_key=SCRAPER_API_KEY)
    await explorer.run_all_tests()
    
    logger.info(f"Exploration completed at {datetime.now()}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Exploration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1) 