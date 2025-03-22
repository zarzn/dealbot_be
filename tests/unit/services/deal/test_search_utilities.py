"""
Unit tests for the search utilities module.
"""

import pytest
from typing import Dict, Any

from core.services.deal.search.search_utils import (
    normalize_text,
    calculate_similarity,
    extract_text_features,
    format_price,
    truncate_text
)


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