"""
Unit tests for the deal creation module.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
from decimal import Decimal
from datetime import datetime

from core.models.enums import MarketCategory, MarketType
from core.services.deal.search.deal_creation import (
    create_deal_from_product,
    create_deal_from_dict,
    get_or_create_deal
)


class TestDealCreation:
    """Tests for the deal creation functionality."""
    
    @pytest.fixture
    def mock_service(self):
        """Return a mock service instance with proper async functionality."""
        mock = MagicMock()
        
        # Set up the database
        mock.db = MagicMock()
        mock_scalar = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = mock_scalar
        mock.db.execute = AsyncMock(return_value=mock_result)
        
        # Set up the repository
        mock._repository = MagicMock()
        mock_deal = MagicMock()
        mock._repository.create = AsyncMock(return_value=mock_deal)
        mock._repository.get_by_external_id = AsyncMock()
        
        # Set up cache deal function
        mock._cache_deal = AsyncMock()
        
        return mock

    @pytest.mark.asyncio
    async def test_create_deal_from_product_basic(self):
        """Test basic deal creation from a product."""
        # Create a mock service instance with properly configured async mocks
        mock_service = MagicMock()
        mock_service._repository = MagicMock()
        mock_service._repository.create = AsyncMock()
        mock_service._cache_deal = AsyncMock()
        mock_service.db = MagicMock()
        
        # Set up execute to be an async mock that returns a result with scalar_one_or_none
        mock_execute = AsyncMock()
        mock_result = MagicMock()
        mock_market = MagicMock()
        mock_market.id = uuid.UUID("8d5eefdf-b25e-49f8-bdcc-9033a59d19cb")
        mock_market.name = "Test Market"
        mock_result.scalar_one_or_none.return_value = mock_market
        mock_execute.return_value = mock_result
        mock_service.db.execute = mock_execute
        
        # Create a mock deal to be returned
        mock_deal = MagicMock()
        mock_deal.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        mock_deal.title = "Test Product"
        mock_service._repository.create.return_value = mock_deal
        
        # Test product data
        product = {
            "title": "Test Product",
            "description": "A great test product",
            "price": 99.99,
            "url": "https://example.com/product",
            "image_url": "https://example.com/image.jpg",
            "seller": "Test Seller",
            "rating": 4.5,
            "review_count": 100
        }
        
        # Call the function with our mock service
        result = await create_deal_from_product(
            mock_service,
            product=product,
            query="test product",
            market_type="amazon",
            user_id=uuid.UUID("00000000-0000-4000-a000-000000000001")
        )
        
        # Assert that repository.create was called
        mock_service._repository.create.assert_called_once()
        
        # Check the data passed to create
        call_args = mock_service._repository.create.call_args[0][0]
        assert call_args["title"] == "Test Product"
        assert call_args["description"] == "A great test product"
        assert call_args["price"] == Decimal("99.99")
        assert call_args["url"] == "https://example.com/product"
        assert call_args["source"] == "Test Market"
        assert isinstance(call_args["market_id"], uuid.UUID)
        
        # Check that seller info was included
        assert "seller_info" in call_args
        assert call_args["seller_info"]["name"] == "Test Seller"
        assert call_args["seller_info"]["rating"] == 4.5
        assert call_args["seller_info"]["reviews"] == 100
        
        # Verify the deal was cached
        mock_service._cache_deal.assert_called_once_with(mock_deal)
        
        # Verify the returned deal
        assert result == mock_deal
    
    @pytest.mark.asyncio
    async def test_create_deal_from_product_missing_required_fields(self):
        """Test create_deal_from_product with missing required fields."""
        # Create a mock service instance
        mock_service = MagicMock()
        
        # Test products with missing required fields
        products = [
            # Missing title
            {
                "description": "A great test product",
                "price": 99.99,
                "url": "https://example.com/product"
            },
            # Missing price
            {
                "title": "Test Product",
                "description": "A great test product",
                "url": "https://example.com/product"
            },
            # Missing URL
            {
                "title": "Test Product",
                "description": "A great test product",
                "price": 99.99
            },
        ]
        
        for product in products:
            result = await create_deal_from_product(
                mock_service,
                product=product,
                query="test product",
                market_type="amazon"
            )
            assert result is None
    
    @pytest.mark.asyncio
    async def test_create_deal_from_product_with_category(self):
        """Test create_deal_from_product with category derived from AI query analysis."""
        # Create a mock service instance
        mock_service = MagicMock()
        mock_service._repository = AsyncMock()
        mock_service._cache_deal = AsyncMock()
        mock_service.db = AsyncMock()
        
        # Mock the query result for market
        mock_market = MagicMock()
        mock_market.id = uuid.uuid4()
        mock_market.name = "Test Market"
        mock_market.type = "amazon"
        
        # Set up execute to return our mock market
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_market
        mock_service.db.execute.return_value = mock_result
        
        # Test product data with AI query analysis
        product = {
            "title": "Test Electronics",
            "description": "A great test product",
            "price": 99.99,
            "url": "https://example.com/product",
            "image_url": "https://example.com/image.jpg",
            "ai_query_analysis": {
                "category": "electronics"
            }
        }
        
        # Call function
        result = await create_deal_from_product(
            mock_service,
            product=product,
            query="test electronics",
            market_type="amazon"
        )
        
        # Verify repository was called with expected category
        mock_service._repository.create.assert_called_once()
        call_args = mock_service._repository.create.call_args[0][0]
        
        # Check that the lowercase category "electronics" was used directly
        assert call_args["category"] == "electronics"
        
        # Test with invalid category in AI analysis
        mock_service._repository.create.reset_mock()
        
        product["ai_query_analysis"]["category"] = "invalid_category"
        
        result = await create_deal_from_product(
            mock_service,
            product=product,
            query="test product",
            market_type="amazon"
        )
        
        # Verify repository was called with default category
        mock_service._repository.create.assert_called_once()
        call_args = mock_service._repository.create.call_args[0][0]
        assert call_args["category"] == MarketCategory.OTHER.value
    
    @pytest.mark.asyncio
    async def test_create_deal_from_product_with_seller_info(self):
        """Test create_deal_from_product with seller information handling."""
        # Create a mock service instance
        mock_service = MagicMock()
        mock_service._repository = AsyncMock()
        mock_service._cache_deal = AsyncMock()
        mock_service.db = AsyncMock()
        
        # Mock the query result for market
        mock_market = MagicMock()
        mock_market.id = uuid.uuid4()
        mock_market.name = "Test Market"
        mock_market.type = "amazon"
        
        # Set up execute to return our mock market
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_market
        mock_service.db.execute.return_value = mock_result
        
        # Test product data with seller info in metadata
        product = {
            "title": "Test Product",
            "description": "A great test product",
            "price": 99.99,
            "url": "https://example.com/product",
            "metadata": {
                "seller": "Metadata Seller",
                "rating": 4.8,
                "review_count": 200,
                "other_key": "other_value"
            }
        }
        
        # Call function
        result = await create_deal_from_product(
            mock_service,
            product=product,
            query="test product",
            market_type="amazon"
        )
        
        # Verify repository was called with expected seller info
        mock_service._repository.create.assert_called_once()
        call_args = mock_service._repository.create.call_args[0][0]
        
        assert call_args["seller_info"]["name"] == "Metadata Seller"
        assert call_args["seller_info"]["rating"] == 4.8
        assert call_args["seller_info"]["reviews"] == 200
        
        # Verify other metadata was preserved
        assert "other_key" in call_args["deal_metadata"]
        assert call_args["deal_metadata"]["other_key"] == "other_value"
    
    @pytest.mark.asyncio
    async def test_create_deal_from_product_with_price_handling(self):
        """Test create_deal_from_product with various price scenarios."""
        # Create a mock service instance
        mock_service = MagicMock()
        mock_service._repository = AsyncMock()
        mock_service._cache_deal = AsyncMock()
        mock_service.db = AsyncMock()
        
        # Mock the query result for market
        mock_market = MagicMock()
        mock_market.id = uuid.uuid4()
        mock_market.name = "Test Market"
        mock_market.type = "amazon"
        
        # Set up execute to return our mock market
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_market
        mock_service.db.execute.return_value = mock_result
        
        # Test cases for price handling
        test_cases = [
            # Negative price should be converted to minimum valid price
            {
                "input": {"price": -10.0, "original_price": 100.0},
                "expected_price": Decimal("0.01"),
                "expected_original_price": Decimal("100.0")
            },
            # String price should be converted to Decimal
            {
                "input": {"price": "25.99", "original_price": "35.99"},
                "expected_price": Decimal("25.99"),
                "expected_original_price": Decimal("35.99")
            },
            # Original price not greater than price should be ignored
            {
                "input": {"price": 50.0, "original_price": 40.0},
                "expected_price": Decimal("50.0"),
                "expected_original_price": None
            }
        ]
        
        for i, case in enumerate(test_cases):
            # Reset mocks for each test case
            mock_service._repository.create.reset_mock()
            
            # Basic product template
            product = {
                "title": f"Test Product {i}",
                "description": "A great test product",
                "url": "https://example.com/product",
                "price": case["input"]["price"],
                "original_price": case["input"]["original_price"]
            }
            
            # Call function
            result = await create_deal_from_product(
                mock_service,
                product=product,
                query=f"test product {i}",
                market_type="amazon"
            )
            
            # Verify repository was called with expected prices
            mock_service._repository.create.assert_called_once()
            call_args = mock_service._repository.create.call_args[0][0]
            
            assert call_args["price"] == case["expected_price"]
            
            if case["expected_original_price"] is not None:
                assert "original_price" in call_args
                assert call_args["original_price"] == case["expected_original_price"]
            else:
                assert "original_price" not in call_args
    
    @pytest.mark.asyncio
    async def test_create_deal_from_product_no_market(self):
        """Test create_deal_from_product when no market is found."""
        # Create a mock service instance
        mock_service = MagicMock()
        mock_service.db = AsyncMock()
        
        # Set up execute to return None for market
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_service.db.execute.return_value = mock_result
        
        # Test product data
        product = {
            "title": "Test Product",
            "description": "A great test product",
            "price": 99.99,
            "url": "https://example.com/product"
        }
        
        # Call function
        result = await create_deal_from_product(
            mock_service,
            product=product,
            query="test product",
            market_type="unknown_market"
        )
        
        # Verify result is None when no market is found
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create_deal_from_dict_success(self):
        """Test basic deal creation from a dictionary."""
        # Create a mock service instance
        mock_service = MagicMock()
        
        # Mock get_or_create_deal to return a new deal
        mock_deal = MagicMock()
        mock_deal.id = uuid.uuid4()
        mock_deal.title = "Test Deal"
        
        mock_service.get_or_create_deal = AsyncMock(return_value=(mock_deal, True))
        
        # Test deal data
        deal_data = {
            "title": "Test Deal",
            "description": "A test deal",
            "price": 49.99,
            "url": "https://example.com/deal",
            "image_url": "https://example.com/image.jpg",
            "external_id": "test-123",
            "market_id": str(uuid.uuid4()),
            "category": "electronics",
            "status": "active",
            "source": "api",
            "metadata": {"key": "value"}
        }
        
        # Call function
        result = await create_deal_from_dict(mock_service, deal_data)
        
        # Verify get_or_create_deal was called with expected args
        mock_service.get_or_create_deal.assert_called_once()
        call_args = mock_service.get_or_create_deal.call_args
        
        assert call_args[1]["external_id"] == "test-123"
        assert isinstance(call_args[1]["market_id"], uuid.UUID)  # Converted from string
        
        # Verify defaults were passed correctly
        defaults = call_args[1]["defaults"]
        assert defaults["title"] == "Test Deal"
        assert defaults["description"] == "A test deal"
        assert defaults["price"] == 49.99
        assert defaults["url"] == "https://example.com/deal"
        assert defaults["image_url"] == "https://example.com/image.jpg"
        assert defaults["category"] == "electronics"
        assert defaults["status"] == "active"
        assert defaults["source"] == "api"
        assert defaults["metadata"] == {"key": "value"}
        
        # Verify result is the mock deal
        assert result == mock_deal
    
    @pytest.mark.asyncio
    async def test_create_deal_from_dict_missing_title(self):
        """Test create_deal_from_dict with missing title."""
        # Create a mock service instance
        mock_service = MagicMock()
        
        # Test deal data with missing title
        deal_data = {
            "description": "A test deal",
            "price": 49.99,
            "url": "https://example.com/deal",
            "external_id": "test-123"
        }
        
        # Call function
        result = await create_deal_from_dict(mock_service, deal_data)
        
        # Verify get_or_create_deal was not called
        mock_service.get_or_create_deal.assert_not_called()
        
        # Verify result is None
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create_deal_from_dict_invalid_price(self):
        """Test create_deal_from_dict with invalid price."""
        # Create a mock service instance
        mock_service = MagicMock()
        
        # Test deal data with invalid price
        deal_data = {
            "title": "Test Deal",
            "description": "A test deal",
            "price": "invalid-price",
            "url": "https://example.com/deal",
            "external_id": "test-123"
        }
        
        # Call function
        result = await create_deal_from_dict(mock_service, deal_data)
        
        # Verify get_or_create_deal was not called
        mock_service.get_or_create_deal.assert_not_called()
        
        # Verify result is None
        assert result is None
    
    @pytest.mark.asyncio
    @patch('core.services.deal.search.deal_creation.select')
    @patch('core.services.deal.search.deal_creation.Deal')
    async def test_get_or_create_deal_existing(self, mock_deal_class, mock_select):
        """Test get_or_create_deal when deal already exists."""
        # Create a mock service instance
        mock_service = MagicMock()
        mock_service.db = AsyncMock()
        
        # Mock existing deal
        mock_deal = MagicMock()
        mock_deal.id = uuid.uuid4()
        mock_deal.title = "Existing Deal"
        
        # Set up a mock where clause
        mock_where_clause = MagicMock()
        mock_select.return_value = mock_where_clause
        mock_where_clause.where.return_value = mock_where_clause
        
        # Set up execute to return our mock deal
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_deal
        mock_service.db.execute.return_value = mock_result
        
        # Test parameters
        external_id = "ext-123"
        market_id = uuid.uuid4()
        defaults = {
            "title": "Test Deal",
            "description": "This is a test deal",
            "price": 99.99
        }
        
        # Call function
        result, is_new = await get_or_create_deal(
            mock_service,
            external_id=external_id,
            market_id=market_id,
            defaults=defaults
        )
        
        # Verify result is the existing deal and is_new is False
        assert result == mock_deal
        assert is_new is False
        
        # Verify db.add was not called (no new deal created)
        mock_service.db.add.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('core.services.deal.search.deal_creation.uuid4')
    async def test_get_or_create_deal_new(self, mock_uuid4):
        """Test get_or_create_deal creates a new deal when none exists."""
        # Create a mock service with appropriately configured DB
        mock_service = MagicMock()
        mock_service.db = MagicMock()
        mock_service.db.execute = AsyncMock()
        mock_service.db.execute.return_value.scalar_one_or_none = AsyncMock(return_value=None)
        mock_service.db.flush = AsyncMock()
        mock_service.db.refresh = AsyncMock()
        
        # Mock uuid4
        test_uuid = uuid.uuid4()
        mock_uuid4.return_value = test_uuid
        
        # Test parameters
        external_id = "ext-123"
        market_id = uuid.uuid4()
        defaults = {
            "title": "Test Deal",
            "description": "This is a test deal",
            "price": 99.99,
            "url": "https://example.com/deal",
            "category": "electronics"
        }
        
        # Import the function directly
        from core.services.deal.search.deal_creation import get_or_create_deal
        
        # Call function with additional patching
        with patch('core.services.deal.search.deal_creation.Deal') as mock_deal_class:
            # Set up mock deal class
            mock_deal_instance = MagicMock()
            mock_deal_class.return_value = mock_deal_instance
            
            # Call function
            result, is_new = await get_or_create_deal(
                mock_service,
                external_id=external_id,
                market_id=market_id,
                defaults=defaults
            )
            
            # Verify mock_deal_class was called with correct arguments
            mock_deal_class.assert_called_once()
            call_kwargs = mock_deal_class.call_args[1]
            
            # Verify id is the test UUID
            assert call_kwargs["id"] == test_uuid
            
            # Verify other deal properties
            assert call_kwargs["market_id"] == market_id
            assert call_kwargs["title"] == "Test Deal"
            
            # Check that external_id is in deal_metadata
            assert "deal_metadata" in call_kwargs
            assert call_kwargs["deal_metadata"]["external_id"] == external_id
            
            # Verify result is the new deal and is_new is True
            assert result == mock_deal_instance
            assert is_new is True
            
            # Verify db.add was called to add the new deal
            mock_service.db.add.assert_called_once_with(mock_deal_instance)
            
            # Verify db.flush and db.refresh were called
            mock_service.db.flush.assert_called_once()
            mock_service.db.refresh.assert_called_once_with(mock_deal_instance)
    
    @pytest.mark.asyncio
    @patch('core.services.deal.search.deal_creation.select')
    @patch('core.services.deal.search.deal_creation.Deal')
    @patch('core.services.deal.search.deal_creation.uuid4')
    async def test_get_or_create_deal_error_fallback(self, mock_uuid4, mock_deal_class, mock_select):
        """Test get_or_create_deal error handling and fallback creation."""
        # Create a mock service instance
        mock_service = MagicMock()
        mock_service.db = AsyncMock()
        
        # Set up mock deal class
        mock_deal_instance = MagicMock()
        mock_deal_class.return_value = mock_deal_instance
        
        # Set up execute to raise an exception the first time (query fails)
        mock_service.db.execute.side_effect = Exception("Test DB error")
        
        # Mock uuid4
        test_uuid = uuid.uuid4()
        mock_uuid4.return_value = test_uuid
        
        # Test parameters
        external_id = "ext-123"
        market_id = uuid.uuid4()
        defaults = {
            "title": "Test Deal",
            "description": "This is a test deal",
            "price": 99.99,
            "category": "electronics"
        }
        
        # Call function
        result, is_new = await get_or_create_deal(
            mock_service,
            external_id=external_id,
            market_id=market_id,
            defaults=defaults
        )
        
        # Verify mock_deal_class was called with correct arguments
        mock_deal_class.assert_called_once()
        call_kwargs = mock_deal_class.call_args[1]
        assert call_kwargs["id"] == test_uuid
        assert call_kwargs["market_id"] == market_id
        assert call_kwargs["title"] == "Test Deal"
        # Check that external_id is in deal_metadata
        assert "deal_metadata" in call_kwargs
        assert call_kwargs["deal_metadata"]["external_id"] == external_id
        
        # Verify result is the fallback deal and is_new is True
        assert result == mock_deal_instance
        assert is_new is True
        
        # Verify db.add was called to add the fallback deal
        mock_service.db.add.assert_called_once_with(mock_deal_instance) 