"""
Post-scraping filtering module.

This module provides functions to filter and score products retrieved from 
scraping operations based on various criteria such as price constraints,
relevance to search terms, brand matching, etc.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import difflib
import math
from collections import Counter

from core.utils.logger import get_logger

logger = get_logger(__name__)

# Constants for scoring
TITLE_MATCH_WEIGHT = 3.0     # Title matches are more important
DESC_MATCH_WEIGHT = 1.0      # Description matches have lower weight
BRAND_MATCH_WEIGHT = 2.0     # Brand matches have high weight
FEATURE_MATCH_WEIGHT = 1.5   # Feature matches have medium weight
PRICE_MATCH_WEIGHT = 1.5     # Price within range is important
RATING_WEIGHT = 0.5          # Rating contributes to score
REVIEW_COUNT_WEIGHT = 0.3    # More reviews means more reliable

# Common stop words to filter out
STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'for', 'nor', 'on', 'at', 'to', 'by',
    'is', 'are', 'was', 'were', 'been', 'be', 'as', 'in', 'of', 'if', 'this',
    'that', 'it', 'its', 'with', 'from', 'has', 'have', 'had', 'do', 'does',
    'did', 'doing', 'will', 'would', 'should', 'can', 'could', 'may', 'might',
    'must', 'shall', 'i', 'you', 'he', 'she', 'they', 'we', 'my', 'your', 'his',
    'her', 'their', 'our', 'me', 'him', 'us', 'them'
}

def extract_price_constraints(query: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract minimum and maximum price constraints from a search query.
    
    Args:
        query: The search query string
        
    Returns:
        Tuple of (min_price, max_price), either of which may be None
    """
    # Normalize query to lowercase
    normalized_query = query.lower()
    
    # Initialize constraints
    min_price = None
    max_price = None
    
    # Pattern for "under $X"
    under_pattern = re.search(r'under\s+\$?(\d+(?:\.\d+)?)', normalized_query)
    if under_pattern:
        max_price = float(under_pattern.group(1))
    
    # Pattern for "over $X"
    over_pattern = re.search(r'over\s+\$?(\d+(?:\.\d+)?)', normalized_query)
    if over_pattern:
        min_price = float(over_pattern.group(1))
    
    # Pattern for "between $X and $Y" or "$X-$Y"
    range_pattern = re.search(r'\$?(\d+(?:\.\d+)?)\s*(?:to|-)\s*\$?(\d+(?:\.\d+)?)', normalized_query)
    if range_pattern:
        min_price = float(range_pattern.group(1))
        max_price = float(range_pattern.group(2))
    
    # Pattern for "less than $X"
    less_than_pattern = re.search(r'less\s+than\s+\$?(\d+(?:\.\d+)?)', normalized_query)
    if less_than_pattern:
        max_price = float(less_than_pattern.group(1))
    
    # Pattern for "more than $X"
    more_than_pattern = re.search(r'more\s+than\s+\$?(\d+(?:\.\d+)?)', normalized_query)
    if more_than_pattern:
        min_price = float(more_than_pattern.group(1))
    
    logger.debug(f"Extracted price constraints: min={min_price}, max={max_price} from '{query}'")
    return min_price, max_price

def extract_search_terms(query: str) -> List[str]:
    """
    Extract meaningful search terms from a query.
    
    Args:
        query: The search query string
        
    Returns:
        List of search terms
    """
    # Convert to lowercase
    normalized_query = query.lower()
    
    # Remove common filler phrases
    fillers = [
        "i want", "i need", "looking for", "find me", "searching for", "can you find",
        "please find", "i'm looking for", "i am looking for", "show me", "get me",
        "find for me", "find me a", "find a"
    ]
    
    for filler in fillers:
        normalized_query = normalized_query.replace(filler, "")
    
    # Remove price constraints
    price_patterns = [
        r'under\s+\$?\d+(?:\.\d+)?',
        r'over\s+\$?\d+(?:\.\d+)?',
        r'\$?\d+(?:\.\d+)?\s*(?:to|-)\s*\$?\d+(?:\.\d+)?',
        r'less\s+than\s+\$?\d+(?:\.\d+)?',
        r'more\s+than\s+\$?\d+(?:\.\d+)?',
        r'between\s+\$?\d+(?:\.\d+)?\s+and\s+\$?\d+(?:\.\d+)?'
    ]
    
    for pattern in price_patterns:
        normalized_query = re.sub(pattern, '', normalized_query)
    
    # Replace non-alphanumeric with spaces
    normalized_query = re.sub(r'[^\w\s]', ' ', normalized_query)
    
    # Split into words and filter out stop words
    words = normalized_query.split()
    search_terms = [word for word in words if word not in STOP_WORDS and len(word) > 1]
    
    logger.debug(f"Extracted search terms: {search_terms} from '{query}'")
    return search_terms

def extract_product_price(product: Dict[str, Any]) -> Optional[float]:
    """
    Extract the price from a product dictionary, handling various formats.
    
    Args:
        product: A product dictionary
        
    Returns:
        Price as a float or None if not found
    """
    if not product:
        return None
    
    # Try direct price field
    if 'price' in product:
        price_value = product['price']
        if isinstance(price_value, (int, float)):
            return float(price_value)
        elif isinstance(price_value, str):
            # Remove currency symbols and commas
            price_str = re.sub(r'[^\d.]', '', price_value)
            try:
                return float(price_str)
            except (ValueError, TypeError):
                pass
    
    # Try price in nested dictionary
    if 'price_data' in product:
        price_data = product['price_data']
        if isinstance(price_data, dict):
            if 'value' in price_data:
                try:
                    return float(price_data['value'])
                except (ValueError, TypeError):
                    pass
            elif 'amount' in price_data:
                try:
                    return float(price_data['amount'])
                except (ValueError, TypeError):
                    pass
    
    # Try original_price field
    if 'original_price' in product:
        try:
            return float(re.sub(r'[^\d.]', '', str(product['original_price'])))
        except (ValueError, TypeError):
            pass
    
    # Try extracting from price_string
    if 'price_string' in product and product['price_string']:
        price_match = re.search(r'\$?(\d+(?:\.\d+)?)', str(product['price_string']))
        if price_match:
            try:
                return float(price_match.group(1))
            except (ValueError, TypeError):
                pass
    
    logger.warning(f"Could not extract price from product: {product.get('title', 'Unknown')}")
    return None

def filter_products_by_price(
    products: List[Dict[str, Any]], 
    min_price: Optional[float], 
    max_price: Optional[float]
) -> List[Dict[str, Any]]:
    """
    Filter products based on price constraints.
    
    Args:
        products: List of product dictionaries
        min_price: Minimum price (optional)
        max_price: Maximum price (optional)
        
    Returns:
        Filtered list of product dictionaries
    """
    if not products:
        return []
    
    # If no price constraints, return all products
    if min_price is None and max_price is None:
        return products
    
    filtered_products = []
    
    for product in products:
        price = extract_product_price(product)
        
        # Skip if price couldn't be extracted
        if price is None:
            logger.debug(f"Skipping price filter for product without price: {product.get('title', 'Unknown')}")
            filtered_products.append(product)
            continue
        
        # Apply min price filter
        if min_price is not None and price < min_price:
            logger.debug(f"Product price ${price} below min price ${min_price}: {product.get('title', 'Unknown')}")
            continue
        
        # Apply max price filter
        if max_price is not None and price > max_price:
            logger.debug(f"Product price ${price} above max price ${max_price}: {product.get('title', 'Unknown')}")
            continue
        
        # Product passed price filters
        filtered_products.append(product)
    
    logger.info(f"Price filter: {len(products)} products -> {len(filtered_products)} products")
    return filtered_products

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate text similarity between two strings.
    
    Args:
        text1: First text string
        text2: Second text string
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0
    
    # Normalize texts
    text1 = text1.lower()
    text2 = text2.lower()
    
    # Calculate similarity using SequenceMatcher
    similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
    return similarity

def calculate_keyword_presence(
    text: str, 
    keywords: List[str], 
    exact_match_bonus: float = 0.3
) -> float:
    """
    Calculate keyword presence in text.
    
    Args:
        text: Text to search in
        keywords: List of keywords to search for
        exact_match_bonus: Bonus for exact matches
        
    Returns:
        Score based on keyword presence (0.0 to 1.0 plus bonuses)
    """
    if not text or not keywords:
        return 0.0
    
    # Normalize text
    text = text.lower()
    normalized_text = re.sub(r'[^\w\s]', ' ', text)
    text_words = set(normalized_text.split())
    
    matches = 0
    total_keywords = len(keywords)
    
    for keyword in keywords:
        keyword = keyword.lower()
        
        # Check for exact word match
        if keyword in text_words:
            matches += 1.0 + exact_match_bonus
        # Check for substring match
        elif keyword in text:
            matches += 0.5
    
    # Normalize score (allowing for bonus to exceed 1.0)
    if total_keywords > 0:
        score = matches / total_keywords
    else:
        score = 0.0
    
    return score

def calculate_relevance_score(
    product: Dict[str, Any],
    search_terms: List[str],
    brands: Optional[List[str]] = None,
    features: Optional[List[str]] = None
) -> float:
    """
    Calculate a relevance score for a product based on search criteria.
    
    Args:
        product: Product dictionary
        search_terms: List of search terms
        brands: List of brands (optional)
        features: List of features (optional)
        
    Returns:
        Relevance score (higher is better)
    """
    if not product or not search_terms:
        return 0.0
    
    score = 0.0
    
    # Get product details
    title = product.get('title', '')
    description = product.get('description', '')
    brand = product.get('brand', '')
    
    # Title relevance (most important)
    title_score = calculate_keyword_presence(title, search_terms, exact_match_bonus=0.5)
    score += title_score * TITLE_MATCH_WEIGHT
    
    # Description relevance
    desc_score = calculate_keyword_presence(description, search_terms, exact_match_bonus=0.2)
    score += desc_score * DESC_MATCH_WEIGHT
    
    # Brand matching
    if brands and brand:
        brand_score = 0.0
        for b in brands:
            if b.lower() in brand.lower():
                brand_score = 1.0
                break
        score += brand_score * BRAND_MATCH_WEIGHT
    
    # Feature matching
    if features:
        feature_text = f"{title} {description}"
        feature_score = calculate_keyword_presence(feature_text, features, exact_match_bonus=0.3)
        score += feature_score * FEATURE_MATCH_WEIGHT
    
    # Rating bonus
    if 'rating' in product and product['rating'] is not None:
        try:
            rating = float(product['rating'])
            # Normalize to 0-1 scale (assuming 5-star scale)
            rating_score = min(rating / 5.0, 1.0)
            score += rating_score * RATING_WEIGHT
        except (ValueError, TypeError):
            pass
    
    # Review count bonus (capped at 100 reviews for normalization)
    if 'reviews_count' in product and product['reviews_count'] is not None:
        try:
            reviews = int(product['reviews_count'])
            # Logarithmic scale to prevent huge review counts from dominating
            review_score = min(math.log(reviews + 1) / math.log(101), 1.0)
            score += review_score * REVIEW_COUNT_WEIGHT
        except (ValueError, TypeError):
            pass
    
    return score

def normalize_scores(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize relevance scores across all products.
    
    Args:
        products: List of product dictionaries with '_relevance_score' field
        
    Returns:
        List of products with normalized scores
    """
    if not products:
        return []
    
    # Find min and max scores
    scores = [p.get('_relevance_score', 0.0) for p in products]
    min_score = min(scores)
    max_score = max(scores)
    
    # Avoid division by zero
    score_range = max_score - min_score
    if score_range == 0:
        # All scores are equal, set to 1.0
        for product in products:
            product['_relevance_score'] = 1.0
        return products
    
    # Normalize scores to 0.0-1.0 range
    for product in products:
        old_score = product.get('_relevance_score', 0.0)
        product['_relevance_score'] = (old_score - min_score) / score_range
    
    return products

def extract_brands_from_query(
    query: str,
    common_brands: Optional[List[str]] = None
) -> List[str]:
    """
    Extract brand names from a query string.
    
    Args:
        query: The search query string
        common_brands: Optional list of common brands to check for
        
    Returns:
        List of identified brands
    """
    if not query:
        return []
    
    # Default list of common brands
    if common_brands is None:
        common_brands = [
            'apple', 'samsung', 'sony', 'lg', 'nike', 'adidas', 'amazon', 'google',
            'microsoft', 'dell', 'hp', 'lenovo', 'asus', 'acer', 'nintendo', 'xbox',
            'playstation', 'dyson', 'kitchenaid', 'cuisinart', 'philips', 'bose',
            'logitech', 'anker', 'belkin', 'intel', 'amd', 'nvidia', 'corsair',
            'razer', 'sennheiser', 'beats', 'jbl', 'bosch', 'shark', 'instant pot'
        ]
    
    # Normalize query
    normalized_query = query.lower()
    
    # Look for brands in the query
    found_brands = []
    for brand in common_brands:
        # Check for exact word match by adding word boundaries
        pattern = r'\b' + re.escape(brand) + r'\b'
        if re.search(pattern, normalized_query, re.IGNORECASE):
            found_brands.append(brand)
    
    logger.debug(f"Extracted brands: {found_brands} from '{query}'")
    return found_brands

def post_process_products(
    products: List[Dict[str, Any]],
    query: str,
    search_terms: Optional[List[str]] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    brands: Optional[List[str]] = None,
    features: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Filter and score products based on the search criteria.
    
    Args:
        products: List of product dictionaries
        query: Original search query
        search_terms: Optional list of search terms (extracted from query if not provided)
        min_price: Minimum price constraint (extracted from query if not provided)
        max_price: Maximum price constraint (extracted from query if not provided)
        brands: Optional list of brands to filter by (extracted from query if not provided)
        features: Optional list of features to look for
        
    Returns:
        Filtered and scored list of products, sorted by relevance score
    """
    if not products:
        logger.warning("No products provided for post-processing")
        return []
    
    logger.info(f"Post-processing {len(products)} products for query: '{query}'")
    
    # Extract parameters if not provided
    if search_terms is None:
        search_terms = extract_search_terms(query)
    
    if min_price is None or max_price is None:
        extracted_min, extracted_max = extract_price_constraints(query)
        min_price = min_price if min_price is not None else extracted_min
        max_price = max_price if max_price is not None else extracted_max
    
    if brands is None:
        brands = extract_brands_from_query(query)
    
    # Step 1: Apply price filtering
    filtered_products = filter_products_by_price(products, min_price, max_price)
    
    if not filtered_products:
        logger.warning("No products remained after price filtering")
        # If price filtering removed all products, be more lenient
        return products
    
    # Step 2: Calculate relevance scores
    for product in filtered_products:
        product['_relevance_score'] = calculate_relevance_score(
            product, search_terms, brands, features
        )
    
    # Step 3: Normalize scores for better comparability
    filtered_products = normalize_scores(filtered_products)
    
    # Step 4: Sort by relevance score (descending)
    filtered_products.sort(key=lambda p: p.get('_relevance_score', 0.0), reverse=True)
    
    logger.info(f"Post-processing completed: {len(filtered_products)} products with scores")
    return filtered_products 