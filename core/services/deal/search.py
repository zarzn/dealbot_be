"""Deal search module (Legacy).

This module is maintained for backward compatibility.
All functionality has been moved to the 'search' package.
"""

# Re-export all functions from the search package
from core.services.deal.search import (
    search_deals,
    discover_deal,
    perform_realtime_scraping as _perform_realtime_scraping,
    search_products as _search_products,
    filter_deals as _filter_deals,
    create_deal_from_product as _create_deal_from_product,
    create_deal_from_dict as _create_deal_from_dict,
    get_or_create_deal as _get_or_create_deal,
    monitor_deals as _monitor_deals,
    fetch_deals_from_api as _fetch_deals_from_api,
    build_search_params as _build_search_params,
    process_and_store_deals as _process_and_store_deals,
    check_expired_deals as _check_expired_deals,
    is_valid_market_category as _is_valid_market_category,
    get_market_id_for_category as _get_market_id_for_category,
    extract_market_type as _extract_market_type,
    extract_product_id as _extract_product_id,
    convert_to_response as _convert_to_response,
    get_optimized_query_for_marketplace,
    post_process_products
)

# For backward compatibility, maintain old function names with underscores
__all__ = [
    'search_deals',
    'discover_deal',
    '_perform_realtime_scraping',
    '_search_products',
    '_filter_deals',
    '_create_deal_from_product',
    '_create_deal_from_dict',
    '_get_or_create_deal',
    '_monitor_deals',
    '_fetch_deals_from_api',
    '_build_search_params',
    '_process_and_store_deals',
    '_check_expired_deals',
    '_is_valid_market_category',
    '_get_market_id_for_category',
    '_extract_market_type',
    '_extract_product_id',
    '_convert_to_response',
    'get_optimized_query_for_marketplace',
    'post_process_products'
]