"""
Deal search package.

This package provides functionality for searching, filtering, and managing deals
across various marketplaces and categories.
"""

# Core search functionality
from core.services.deal.search.core_search import search_deals, discover_deal

# Real-time scraping
from core.services.deal.search.realtime import perform_realtime_scraping, search_products

# Deal filtering
from core.services.deal.search.filters import filter_deals

# Deal creation
from core.services.deal.search.deal_creation import (
    create_deal_from_product,
    create_deal_from_dict,
    get_or_create_deal
)

# Deal monitoring
from core.services.deal.search.monitoring import (
    monitor_deals,
    process_and_store_deals,
    check_expired_deals
)

# Utility functions
from core.services.deal.search.utils import (
    is_valid_market_category,
    get_market_id_for_category,
    extract_market_type,
    extract_product_id,
    convert_to_response
)

# Query formatting
from core.services.deal.search.query_formatter import get_optimized_query_for_marketplace

# Post-scraping filtering
from core.services.deal.search.post_scraping_filter import post_process_products

__all__ = [
    # Core search
    'search_deals',
    'discover_deal',
    
    # Real-time scraping
    'perform_realtime_scraping',
    'search_products',
    
    # Deal filtering
    'filter_deals',
    
    # Deal creation
    'create_deal_from_product',
    'create_deal_from_dict',
    'get_or_create_deal',
    
    # Deal monitoring
    'monitor_deals',
    'process_and_store_deals',
    'check_expired_deals',
    
    # Utility functions
    'is_valid_market_category',
    'get_market_id_for_category',
    'extract_market_type',
    'extract_product_id',
    'convert_to_response',
    
    # Query formatting
    'get_optimized_query_for_marketplace',
    
    # Post-scraping filtering
    'post_process_products'
] 