"""Utility functions for Oxylabs web scraping."""

import logging
import re
import hashlib
from typing import Any, Dict, Optional, Tuple, Union, List

logger = logging.getLogger(__name__)


def extract_price(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Extract price and currency from text.
    
    Args:
        text: Text containing price information
        
    Returns:
        Tuple of (price as float, currency symbol)
    """
    if not text:
        return None, None
    
    # Remove any non-breaking spaces and other whitespace
    text = text.replace("\xa0", " ").strip()
    
    # Common currency symbols and their codes
    currency_map = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "¥": "JPY",
        "₹": "INR",
        "₽": "RUB",
        "₩": "KRW",
        "A$": "AUD",
        "C$": "CAD",
        "HK$": "HKD",
        "元": "CNY",
        "₿": "BTC",
    }
    
    # Check for currency codes like USD, EUR, etc.
    currency_code_pattern = r"(USD|EUR|GBP|JPY|CNY|AUD|CAD|CHF|SEK|NZD|MXN|SGD|HKD|NOK|KRW|TRY|RUB|INR|BRL|ZAR|DKK|PLN|THB|IDR|HUF|CZK|ILS|CLP|PHP|AED|COP|SAR|MYR|RON)"
    code_match = re.search(currency_code_pattern, text)
    
    # Try to extract the price and currency symbol
    price_pattern = r"([\$\€\£\¥\₹\₽\₩])\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*([\$\€\£\¥\₹\₽\₩])"
    match = re.search(price_pattern, text)
    
    if match:
        groups = match.groups()
        if groups[0] and groups[1]:  # Symbol before number
            symbol, price_str = groups[0], groups[1]
        elif groups[2] and groups[3]:  # Number before symbol
            price_str, symbol = groups[2], groups[3]
        else:
            return None, None
        
        price_str = price_str.replace(",", ".")
        try:
            price = float(price_str)
            currency = currency_map.get(symbol, symbol)
            return price, currency
        except ValueError:
            logger.warning(f"Failed to convert price string to float: {price_str}")
            return None, None
    elif code_match:
        # If we found a currency code, try to extract the numeric part
        currency_code = code_match.group(1)
        numeric_pattern = r"(\d+(?:[.,]\d+)?)"
        numeric_match = re.search(numeric_pattern, text)
        
        if numeric_match:
            price_str = numeric_match.group(1).replace(",", ".")
            try:
                price = float(price_str)
                return price, currency_code
            except ValueError:
                logger.warning(f"Failed to convert price string to float: {price_str}")
                return None, None
    
    # Regular expression for numbers with currency code format (e.g., "29.99 USD")
    amount_with_code = r"(\d+(?:[.,]\d+)?)\s*" + currency_code_pattern
    amount_code_match = re.search(amount_with_code, text)
    
    if amount_code_match:
        price_str = amount_code_match.group(1).replace(",", ".")
        currency_code = amount_code_match.group(2)
        try:
            price = float(price_str)
            return price, currency_code
        except ValueError:
            logger.warning(f"Failed to convert price string to float: {price_str}")
            return None, None
    
    # Last attempt - just try to find any number
    just_number = r"(\d+(?:[.,]\d+)?)"
    number_match = re.search(just_number, text)
    
    if number_match:
        price_str = number_match.group(1).replace(",", ".")
        try:
            price = float(price_str)
            # No currency identified
            return price, None
        except ValueError:
            logger.warning(f"Failed to convert price string to float: {price_str}")
            return None, None
    
    return None, None


def detect_currency(price_text: str) -> Optional[str]:
    """Detect currency from price text.
    
    Args:
        price_text: Text containing price information
        
    Returns:
        Currency code if detected, None otherwise
    """
    if not price_text:
        return None
    
    # Common currency symbols and their codes
    currency_map = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "¥": "JPY",
        "₹": "INR",
        "₽": "RUB",
        "₩": "KRW",
        "A$": "AUD",
        "C$": "CAD",
        "元": "CNY",
    }
    
    # Try to extract currency symbol
    symbol_pattern = r"([\$\€\£\¥\₹\₽\₩])"
    symbol_match = re.search(symbol_pattern, price_text)
    
    if symbol_match:
        symbol = symbol_match.group(1)
        return currency_map.get(symbol, symbol)
    
    # Check for currency codes
    code_pattern = r"(USD|EUR|GBP|JPY|CNY|AUD|CAD|CHF|SEK|NZD|MXN|SGD|HKD|NOK|KRW|TRY|RUB|INR|BRL|ZAR|DKK|PLN|THB|IDR|HUF|CZK|ILS|CLP|PHP|AED|COP|SAR|MYR|RON)"
    code_match = re.search(code_pattern, price_text)
    
    if code_match:
        return code_match.group(1)
    
    return None


def clean_html(html_content: str) -> str:
    """Remove HTML tags from content.
    
    Args:
        html_content: HTML content to clean
        
    Returns:
        Cleaned text
    """
    if not html_content:
        return ""
    
    # Remove HTML tags
    clean_text = re.sub(r"<[^>]*>", "", html_content)
    
    # Remove extra whitespace
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    
    return clean_text 

# Compile regular expression pattern once for better performance
PRICE_PATTERN = re.compile(r'(\d+\.?\d*|\.\d+)')

def generate_product_id(source: str, title: str, merchant: str = "", price: Any = None, existing_id: str = "") -> str:
    """Generate a consistent product ID from product details.
    
    Args:
        source: Source marketplace (amazon, walmart, google_shopping)
        title: Product title
        merchant: Merchant/seller name
        price: Price (can be string, float, or object with value)
        existing_id: Existing ID to use if available
        
    Returns:
        Generated product ID string
    """
    # If there's an existing ID that seems valid, use it
    if existing_id and len(existing_id) > 5:
        # For Amazon ASINs, prepend source for consistency
        if source.lower() == "amazon" and len(existing_id) == 10:
            return f"amazon_{existing_id}"
        return existing_id
    
    # Build ID parts for a consistent, readable ID
    id_parts = []
    
    # Start with the source
    id_parts.append(source.lower() if isinstance(source, str) else "unknown")
    
    # Add title (simplified)
    if title and isinstance(title, str):
        # Remove special characters, lowercase, and join words with underscores
        simplified_title = "_".join(
            re.sub(r'[^a-zA-Z0-9\s]', '', title.lower()).split()
        )[:50]  # Limit length
        id_parts.append(simplified_title)
        
    # Add merchant if available
    if merchant and isinstance(merchant, str):
        simplified_merchant = re.sub(r'[^a-zA-Z0-9\s]', '', merchant.lower())
        id_parts.append(simplified_merchant[:20])  # Limit length
        
    # Add price if available
    if price is not None:
        try:
            # Try to convert price to float and format it
            price_float = float(price)
            id_parts.append(f"{price_float:.2f}")
        except (ValueError, TypeError):
            # If conversion fails, try to use it as a string
            if isinstance(price, str):
                # Extract numbers from price string
                price_nums = PRICE_PATTERN.findall(price)
                if price_nums:
                    id_parts.append(price_nums[0])
    
    # Join parts with a separator
    id_string = "_".join(id_parts)
    
    # Generate a hash of the combined string
    id_hash = hashlib.md5(id_string.encode()).hexdigest()[:12]
    
    # Return a formatted ID
    return f"{source.lower() if isinstance(source, str) else 'unknown'}_{id_hash}"

def validate_product_url(url: str, query: str = "", source: str = "", skip_if_validated: bool = True) -> str:
    """Validate and fix product URLs.
    
    Args:
        url: Product URL to validate
        query: Original search query (for relevance check)
        source: Source marketplace (amazon, walmart, etc.)
        skip_if_validated: Skip validation if URL seems valid
        
    Returns:
        Validated/fixed URL or original if couldn't be fixed
    """
    if not url:
        return ""
        
    # Skip validation for already valid URLs if requested
    if skip_if_validated and url.startswith(('http://', 'https://')):
        return url
        
    # Check for different URL patterns and fix them
    
    # Handle Amazon URLs
    if source.lower() == 'amazon' or '/dp/' in url or '/gp/product/' in url:
        # Fix URLs like /dp/B07XXXXXXXC
        if url.startswith('/dp/'):
            return f"https://www.amazon.com{url}"
        # Fix URLs like dp/B07XXXXXXXC
        elif url.startswith('dp/'):
            return f"https://www.amazon.com/{url}"
        # Fix URLs like B07XXXXXXXC (ASIN only)
        elif re.match(r'^[A-Z0-9]{10}$', url):
            return f"https://www.amazon.com/dp/{url}"
            
    # Handle Walmart URLs
    elif source.lower() == 'walmart' or '/ip/' in url:
        # Fix URLs like /ip/123456789
        if url.startswith('/ip/'):
            return f"https://www.walmart.com{url}"
        # Fix URLs like ip/123456789
        elif url.startswith('ip/'):
            return f"https://www.walmart.com/{url}"
            
    # Handle eBay URLs
    elif source.lower() == 'ebay' or '/itm/' in url:
        # Fix URLs like /itm/123456789
        if url.startswith('/itm/'):
            return f"https://www.ebay.com{url}"
        # Fix URLs like itm/123456789
        elif url.startswith('itm/'):
            return f"https://www.ebay.com/{url}"
            
    # Handle Google Shopping URLs
    elif source.lower() == 'google_shopping':
        # Fix URLs like /shopping/product/123456789
        if url.startswith('/shopping/product/'):
            return f"https://www.google.com{url}"
        # Fix URLs like shopping/product/123456789
        elif url.startswith('shopping/product/'):
            return f"https://www.google.com/{url}"
            
    # If it already starts with http/https, return as is
    if url.startswith(('http://', 'https://')):
        return url
        
    # Last resort: if no other pattern matched but source is known, try to construct a URL
    if source.lower() == 'amazon':
        # Check if it might be an ASIN
        if re.match(r'^[A-Z0-9]{10}$', url):
            return f"https://www.amazon.com/dp/{url}"
        return f"https://www.amazon.com/{url}"
    elif source.lower() == 'walmart':
        return f"https://www.walmart.com/{url}"
    elif source.lower() == 'ebay':
        return f"https://www.ebay.com/{url}"
    elif source.lower() == 'google_shopping':
        return f"https://www.google.com/{url}"
        
    # If we couldn't fix it, return the original
    return url

def create_standardized_product(
    item: Dict[str, Any],
    source: str,
    query: str = ""
) -> Dict[str, Any]:
    """Create a standardized product object from scraped data.
    
    Args:
        item: Raw product data from scraper
        source: Source marketplace (amazon, walmart, google_shopping)
        query: Original search query (for URL validation)
        
    Returns:
        Dict: Standardized product object
    """
    # Extract basic fields with fallbacks
    title = item.get('title', '') or item.get('name', '')
    
    # Get or generate product ID
    product_id = generate_product_id(
        source=source,
        title=title,
        merchant=item.get('merchant', '') or item.get('seller', ''),
        price=item.get('price', ''),
        existing_id=item.get('id', '') or item.get('asin', '') or item.get('product_id', '')
    )
    
    # Extract price
    price_raw = item.get('price', 0)
    price_value, currency = extract_price(str(price_raw) if not isinstance(price_raw, (int, float)) else "")
    
    if price_value is None:
        # If extraction from string failed, try direct conversion
        try:
            price_value = float(price_raw)
        except (ValueError, TypeError):
            price_value = 0.0
    
    # Determine currency
    if not currency:
        currency = "USD"  # Default
        if isinstance(item.get('price'), str):
            detected_currency = detect_currency(item.get('price', ''))
            if detected_currency:
                currency = detected_currency
        elif 'currency' in item and item['currency']:
            currency = item['currency']
    
    # Handle image URL
    image_url = (
        item.get('image', '') or 
        item.get('thumbnail', '') or 
        (item.get('images', [{}])[0].get('url') if item.get('images') else '')
    )
    
    # Validate and process product URL
    product_url = item.get('link', '') or item.get('url', '')
    product_url = validate_product_url(
        product_url, 
        query=query, 
        source=source,
        skip_if_validated=True
    )
    
    # Create metadata with common fields
    metadata = {
        "seller": item.get('merchant', '') or item.get('seller', ''),
        "rating": item.get('rating', 0),
        "reviews": item.get('reviews', 0),
    }
    
    # Add source-specific metadata
    if source == "amazon":
        metadata["asin"] = item.get('asin', '') or product_id
        metadata["prime"] = item.get('prime', False)
    
    # Create the standardized product object
    return {
        "id": product_id,
        "title": title,
        "price": price_value,
        "currency": currency,
        "image": image_url,
        "url": product_url,
        "description": item.get('description', '') or item.get('snippet', ''),
        "source": source,
        "metadata": metadata
    }

def process_product_batch(
    items: List[Dict[str, Any]],
    source: str,
    query: str = "",
    max_results: int = 50,
    content_extraction_paths: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Process a batch of products more efficiently.
    
    Args:
        items: List of raw product items
        source: Source marketplace (amazon, walmart, google_shopping)
        query: Original search query
        max_results: Maximum number of results to return
        content_extraction_paths: Optional list of JSON paths to extract content
        
    Returns:
        List of standardized product objects
    """
    if not items or not isinstance(items, list):
        logger.warning(f"No valid items to process for {source}")
        return []
        
    processed_products = []
    seen_product_ids = set()  # To avoid duplicates
    
    # Process all items
    for item in items:
        if not isinstance(item, dict):
            continue
            
        try:
            # Check for nested content
            if 'content' in item and isinstance(item['content'], dict):
                content = item['content']
                
                # If specific content extraction paths provided, check them
                if content_extraction_paths:
                    for path in content_extraction_paths:
                        if path in content and isinstance(content[path], list):
                            # Process items from this path
                            nested_items = content[path]
                            for nested_item in nested_items:
                                if not isinstance(nested_item, dict):
                                    continue
                                    
                                # Process each nested item    
                                try:
                                    product = create_standardized_product(
                                        nested_item, 
                                        source=source,
                                        query=query
                                    )
                                    
                                    if product and product['id'] not in seen_product_ids:
                                        seen_product_ids.add(product['id'])
                                        processed_products.append(product)
                                        
                                        if len(processed_products) >= max_results:
                                            return processed_products
                                except Exception as e:
                                    logger.warning(f"Error processing nested {source} item from {path}: {str(e)}")
            
            # Process the item directly
            product = create_standardized_product(
                item, 
                source=source,
                query=query
            )
            
            # Skip if we've already seen this product ID
            if product['id'] in seen_product_ids:
                continue
                
            seen_product_ids.add(product['id'])
            processed_products.append(product)
            
            # Respect max_results limit
            if len(processed_products) >= max_results:
                return processed_products
                
        except Exception as e:
            logger.warning(f"Error processing {source} item: {str(e)}")
    
    return processed_products 