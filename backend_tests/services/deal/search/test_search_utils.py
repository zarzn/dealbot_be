#!/usr/bin/env python3
"""
Unit tests for the utility methods in the DealService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import select
from core.services.deal.base import DealService
from core.models.deal import Deal
from core.models.enums import DealStatus
from core.services.deal.search.search_utils import (
    normalize_text,
    calculate_similarity,
    extract_text_features,
    format_price,
    truncate_text
)


class TestUtilityMethods:
    """Test utility methods used in the DealService."""

    @pytest.mark.unit
    @patch('sqlalchemy.select')
    @patch('sqlalchemy.ext.asyncio.AsyncSession.execute')
    async def test_create_deal_from_dict(self, mock_execute, mock_select):
        """Test creating a deal from a dictionary of data."""
        # Setup mock
        db = AsyncMock()
        
        # Create the service
        service = DealService(db)
        
        # Mock the result set for the market query
        mock_market = MagicMock()
        mock_market.id = uuid.UUID('89ffe811-91e6-4878-8b6b-763b2f8a2e5d')
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_market
        mock_execute.return_value = mock_result
        
        # Deal data
        deal_data = {
            'title': 'Test Deal',
            'description': 'This is a test deal',
            'price': 99.99,
            'url': 'https://example.com',
            'source': 'unit_test',
            'market_id': '89ffe811-91e6-4878-8b6b-763b2f8a2e5d',
            'image_url': 'https://example.com/image.jpg',
            'category': 'electronics'
        }
        
        # Mock the Deal creation through repository
        service._repository = AsyncMock()
        mock_deal = MagicMock()
        mock_deal.id = uuid.UUID('12345678-1234-5678-1234-567812345678')
        mock_deal.title = 'Test Deal'
        service._repository.create.return_value = mock_deal
        
        # Test creating the deal
        result = await service.create_deal_from_dict(deal_data)
        
        # Assertions
        assert result is not None
        assert result.id == mock_deal.id
        assert result.title == 'Test Deal'
        service._repository.create.assert_called_once()

    @pytest.mark.unit
    @patch('sqlalchemy.ext.asyncio.AsyncSession.execute')
    async def test_create_deal_from_dict_existing_deal(self, mock_execute):
        """Test creating a deal that already exists."""
        # Setup mock
        db = AsyncMock()
        
        # Create the service
        service = DealService(db)
        service._repository = AsyncMock()
        
        # Mock the result set for the market query
        mock_market = MagicMock()
        mock_market.id = uuid.UUID('89ffe811-91e6-4878-8b6b-763b2f8a2e5d')
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_market
        mock_execute.return_value = mock_result
        
        # Create a mock Deal with an existing external_id
        with patch('core.models.deal.Deal', MagicMock) as MockDeal:
            # Mock the Deal class to avoid TrackedDeal KeyError
            mock_deal_instance = MagicMock()
            mock_deal_instance.id = uuid.UUID('39f97a94-169b-42eb-be43-298a88edf861')
            mock_deal_instance.title = 'Existing Deal'
            mock_deal_instance.external_id = 'existing123'
            MockDeal.return_value = mock_deal_instance
            
            # Mock finding the existing deal
            mock_existing_result = MagicMock()
            mock_existing_result.scalar_one_or_none.return_value = mock_deal_instance
            mock_execute.side_effect = [mock_result, mock_existing_result]
            
            # Deal data with existing external_id
            deal_data = {
                'title': 'Existing Deal',
                'description': 'This deal already exists',
                'price': 149.99,
                'url': 'https://example.com/existing',
                'source': 'realtime_search',
                'market_id': '89ffe811-91e6-4878-8b6b-763b2f8a2e5d',
                'image_url': 'https://example.com/existing.jpg',
                'external_id': 'existing123',
                'category': 'Home',
                'status': 'active'
            }
            
            # Mock repository
            service._repository.create.return_value = mock_deal_instance
            service._repository.update.return_value = mock_deal_instance
            
            # Test creating/updating the deal
            result = await service.create_deal_from_dict(deal_data)
            
            # Assertions
            assert result is not None
            assert result.id == mock_deal_instance.id
            assert result.title == 'Existing Deal'

    @pytest.mark.unit
    async def test_create_deal_from_dict_invalid_data(self):
        """Test creating a deal with invalid data."""
        # Setup mock
        db = AsyncMock()
        
        # Create the service
        service = DealService(db)
        
        # Invalid data (missing required fields)
        invalid_data = {
            'title': 'Invalid Deal'
        }
        
        # Test creating with invalid data
        with pytest.raises(Exception):
            await service.create_deal_from_dict(invalid_data)


class TestSearchUtils:
    """Tests for the search utilities module."""

    def test_normalize_text(self):
        """Test text normalization function."""
        # Test basic normalization
        assert normalize_text("  Hello  World  ") == "hello world"
        
        # Test empty string
        assert normalize_text("") == ""
        
        # Test None value
        assert normalize_text(None) == ""
        
        # Test mixed case and extra whitespace
        assert normalize_text("  HELLO   world  ") == "hello world"

    def test_calculate_similarity(self):
        """Test similarity calculation between texts."""
        # Test exact match
        assert calculate_similarity("hello world", "hello world") == 1.0
        
        # Test case insensitivity
        assert calculate_similarity("HELLO WORLD", "hello world") == 1.0
        
        # Test partial match
        similarity = calculate_similarity("hello world", "hello there")
        assert 0 < similarity < 1.0
        
        # Test no match
        similarity = calculate_similarity("hello world", "goodbye universe")
        assert similarity < 0.5
        
        # Test with empty strings
        assert calculate_similarity("", "") == 0.0
        assert calculate_similarity("hello", "") == 0.0
        assert calculate_similarity("", "hello") == 0.0
        
        # Test with None values
        assert calculate_similarity(None, "hello") == 0.0
        assert calculate_similarity("hello", None) == 0.0
        assert calculate_similarity(None, None) == 0.0

    def test_extract_text_features(self):
        """Test extracting features from text."""
        # Test basic extraction
        features = extract_text_features("Hello world, this is a test with 123 and 456.78 numbers.")
        assert "hello" in features["keywords"]
        assert "world" in features["keywords"]
        assert "test" in features["keywords"]
        assert 123 in features["numbers"]
        assert 456.78 in features["numbers"]
        assert "hello world" in features["phrases"]
        
        # Test empty text
        features = extract_text_features("")
        assert features["keywords"] == []
        assert features["numbers"] == []
        assert features["phrases"] == []
        
        # Test None value
        features = extract_text_features(None)
        assert features["keywords"] == []
        assert features["numbers"] == []
        assert features["phrases"] == []

    def test_format_price(self):
        """Test price formatting function."""
        # Test numeric formats
        assert format_price(123) == 123.0
        assert format_price(45.67) == 45.67
        
        # Test string formats
        assert format_price("123") == 123.0
        assert format_price("45.67") == 45.67
        assert format_price("$123") == 123.0
        assert format_price("$45.67") == 45.67
        assert format_price("123 USD") == 123.0
        assert format_price("1,234.56") == 1234.56
        
        # Test None value
        assert format_price(None) is None
        
        # Test invalid formats
        assert format_price("abc") is None
        assert format_price("") is None

    def test_truncate_text(self):
        """Test text truncation function."""
        # Test no truncation needed
        assert truncate_text("short text", 20) == "short text"
        
        # Test with truncation
        assert truncate_text("this is a longer text", 10) == "this is a..."
        
        # Test with truncation but no ellipsis
        assert truncate_text("this is a longer text", 10, False) == "this is a"
        
        # Test with empty string
        assert truncate_text("", 10) == ""
        
        # Test with None
        assert truncate_text(None, 10) == "" 