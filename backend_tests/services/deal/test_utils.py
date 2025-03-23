"""
Unit tests for the deal search utils module.
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid5, NAMESPACE_DNS

from core.services.deal.search.utils import (
    is_valid_market_category,
    get_market_id_for_category,
    extract_market_type,
    extract_product_id,
    convert_to_response
)
from core.models.enums import MarketCategory, MarketType


class TestDealSearchUtils:
    """Tests for the deal search utilities."""
    
    def test_extract_market_type(self):
        """Test extracting market type from product URLs."""
        # Test Amazon URL
        amazon_url = "https://www.amazon.com/dp/B08L5TNGMD"
        result = extract_market_type(amazon_url)
        assert result == MarketType.AMAZON
        
        # Test Walmart URL
        walmart_url = "https://www.walmart.com/ip/123456"
        result = extract_market_type(walmart_url)
        assert result == MarketType.WALMART
        
        # Test eBay URL
        ebay_url = "https://www.ebay.com/itm/123456"
        result = extract_market_type(ebay_url)
        assert result == MarketType.EBAY
        
        # Test Google Shopping URL
        google_url = "https://www.google.com/shopping/product/12345"
        result = extract_market_type(google_url)
        assert result == MarketType.GOOGLE_SHOPPING
        
        # Test BestBuy URL
        bestbuy_url = "https://www.bestbuy.com/site/product.p"
        result = extract_market_type(bestbuy_url)
        assert result == MarketType.BESTBUY
        
        # Test unknown URL
        unknown_url = "https://www.example.com/product/12345"
        result = extract_market_type(unknown_url)
        assert result is None
        
        # Test None URL
        result = extract_market_type(None)
        assert result is None
        
        # Test empty URL
        result = extract_market_type("")
        assert result is None
    
    def test_extract_product_id(self):
        """Test extracting product IDs from URLs."""
        # Test Amazon URL with /dp/ format
        amazon_url = "https://www.amazon.com/dp/B08L5TNGMD"
        result = extract_product_id(amazon_url)
        assert result == "B08L5TNGMD"
        
        # Test Amazon URL with /product/ format
        amazon_product_url = "https://www.amazon.com/gp/product/B08L5TNGMD"
        result = extract_product_id(amazon_product_url)
        assert result == "B08L5TNGMD"
        
        # Test Walmart URL
        walmart_url = "https://www.walmart.com/ip/123456"
        result = extract_product_id(walmart_url)
        assert result == "123456"
        
        # Test eBay URL
        ebay_url = "https://www.ebay.com/itm/123456"
        result = extract_product_id(ebay_url)
        assert result == "123456"
        
        # Test Best Buy URL
        bestbuy_url = "https://www.bestbuy.com/site/12345.p"
        result = extract_product_id(bestbuy_url)
        assert result == "12345"
        
        # Test unknown URL
        unknown_url = "https://www.example.com/product/12345"
        result = extract_product_id(unknown_url)
        assert result is None
        
        # Test None URL
        result = extract_product_id(None)
        assert result is None
        
        # Test empty URL
        result = extract_product_id("")
        assert result is None
    
    @patch('core.services.deal.search.utils.MarketCategory')
    def test_is_valid_market_category(self, mock_market_category):
        """Test validating market categories."""
        # Create a test instance
        test_instance = MagicMock()
        
        # Setup MarketCategory mock to return appropriate values
        mock_market_category.__iter__.return_value = [
            MagicMock(value="electronics"),
            MagicMock(value="clothing"),
            MagicMock(value="books")
        ]
        
        # Test valid category (uppercase)
        assert is_valid_market_category(test_instance, "ELECTRONICS") is True
        
        # Test valid category (lowercase)
        assert is_valid_market_category(test_instance, "electronics") is True
        
        # Test valid category (mixed case)
        assert is_valid_market_category(test_instance, "Electronics") is True
        
        # Test invalid category
        assert is_valid_market_category(test_instance, "INVALID_CATEGORY") is False
        
        # Test None category
        assert is_valid_market_category(test_instance, None) is False
        
        # Test empty string
        assert is_valid_market_category(test_instance, "") is False
    
    @patch('uuid.uuid5')
    def test_get_market_id_for_category(self, mock_uuid5):
        """Test getting market ID for a category."""
        # Create a test instance
        test_instance = MagicMock()
        
        # Create mock UUIDs for our test cases
        electronics_uuid = UUID('11111111-1111-1111-1111-111111111111')
        invalid_uuid = UUID('22222222-2222-2222-2222-222222222222')
        default_uuid = UUID('33333333-3333-3333-3333-333333333333')
        
        # Setup the uuid5 mock to return our expected values based on the category name
        def mock_uuid5_side_effect(namespace, name):
            if name == "electronics":
                return electronics_uuid
            elif name == "invalid_category":
                return invalid_uuid
            elif name == "default_market":
                return default_uuid
            return UUID('00000000-0000-0000-0000-000000000000')
        
        mock_uuid5.side_effect = mock_uuid5_side_effect
        
        # Test with valid category
        # The function will use the actual category name regardless of validity
        result = get_market_id_for_category(test_instance, "electronics")
        mock_uuid5.assert_called_with(NAMESPACE_DNS, "electronics")
        assert result == electronics_uuid
        
        # Test with invalid category - it should still use the category name directly
        result = get_market_id_for_category(test_instance, "invalid_category")
        mock_uuid5.assert_called_with(NAMESPACE_DNS, "invalid_category")
        assert result == invalid_uuid
        
        # Test with error in uuid5
        # First call raises exception, second call returns default_uuid
        mock_uuid5.reset_mock()
        mock_uuid5.side_effect = [Exception("Test exception"), default_uuid]
        
        result = get_market_id_for_category(test_instance, "electronics")
        
        # Should have been called twice
        assert mock_uuid5.call_count == 2
        
        # First call should be with the category name
        assert mock_uuid5.call_args_list[0][0] == (NAMESPACE_DNS, "electronics")
        
        # Second call (in exception handler) should be with "default_market"
        assert mock_uuid5.call_args_list[1][0] == (NAMESPACE_DNS, "default_market")
        
        # Final result should be the default UUID
        assert result == default_uuid
    
    def test_convert_to_response(self):
        """Test converting a database model to an API response."""
        # Create a test instance
        test_instance = MagicMock()
        
        # Create a mock model with attributes
        mock_deal = MagicMock()
        mock_deal.id = UUID("11111111-1111-1111-1111-111111111111")
        mock_deal.title = "Test Product"
        mock_deal.description = "This is a test product"
        mock_deal.price = 99.99
        mock_deal.original_price = 149.99
        mock_deal.currency = "USD"
        mock_deal.url = "https://example.com/product"
        mock_deal.image_url = "https://example.com/image.jpg"
        mock_deal.category = "ELECTRONICS"
        mock_deal.status = "active"
        mock_deal.found_at = MagicMock()
        mock_deal.found_at.isoformat.return_value = "2021-01-01T00:00:00"
        mock_deal.expires_at = MagicMock()
        mock_deal.expires_at.isoformat.return_value = "2021-01-31T00:00:00"
        mock_deal.source = "amazon"
        mock_deal.metadata = {"key": "value"}
        
        # Create a mock market
        mock_market = MagicMock()
        mock_market.id = UUID("22222222-2222-2222-2222-222222222222")
        mock_market.name = "Test Market"
        mock_market.type = "amazon"
        mock_deal.market = mock_market
        
        # Test basic conversion
        result = convert_to_response(test_instance, mock_deal)
        assert result["id"] == str(mock_deal.id)
        assert result["title"] == mock_deal.title
        assert result["description"] == mock_deal.description
        assert result["price"] == mock_deal.price
        assert result["original_price"] == mock_deal.original_price
        assert result["currency"] == mock_deal.currency
        assert result["url"] == mock_deal.url
        assert result["image_url"] == mock_deal.image_url
        assert result["category"] == mock_deal.category
        assert result["status"] == mock_deal.status
        assert result["found_at"] == "2021-01-01T00:00:00"
        assert result["expires_at"] == "2021-01-31T00:00:00"
        assert result["source"] == mock_deal.source
        assert result["metadata"] == mock_deal.metadata
        
        # Test with market
        assert "market" in result
        assert result["market"]["id"] == str(mock_market.id)
        assert result["market"]["name"] == mock_market.name
        assert result["market"]["type"] == mock_market.type
        
        # Test with user_id
        # Setup repository mock
        test_instance._repository = MagicMock()
        test_instance._repository.is_deal_saved_by_user.return_value = True
        
        user_id = UUID("33333333-3333-3333-3333-333333333333")
        result = convert_to_response(test_instance, mock_deal, user_id)
        assert "user_actions" in result
        assert result["user_actions"]["is_saved"] is True
        
        # Test with AI analysis
        mock_deal.ai_analysis = {"relevance": 0.85}
        result = convert_to_response(test_instance, mock_deal, include_ai_analysis=True)
        assert "ai_analysis" in result
        assert result["ai_analysis"]["relevance"] == 0.85