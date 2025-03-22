"""
Unit tests for the query formatter module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.services.deal.search.query_formatter import (
    format_search_query_fallback,
    format_search_query_with_ai,
    extract_parameters_from_query,
    get_optimized_query_for_marketplace
)
from core.services.ai import AIService


class TestQueryFormatter:
    """Test suite for the query formatter module."""

    def test_fallback_formatter_removes_fillers(self):
        """Test that fallback formatter removes common filler phrases."""
        # Test various filler phrases
        test_cases = [
            ("find me a laptop", "laptop"),
            ("i want a new phone under $500", "new phone under $500"),
            ("looking for headphones", "headphones"),
            ("can you find gaming mouse", "gaming mouse"),
            ("please find bluetooth speakers", "bluetooth speakers"),
            ("i'm looking for a monitor", "monitor"),
        ]
        
        for input_query, expected_output in test_cases:
            result = format_search_query_fallback(input_query)
            assert result == expected_output

    def test_fallback_formatter_preserves_price_constraints(self):
        """Test that fallback formatter preserves price constraints."""
        test_cases = [
            ("laptop under $500", "laptop under $500"),
            ("headphones $20-$50", "headphones $20-$50"),
            ("phone over $300", "phone over $300"),
            ("TV less than $1000", "TV under $1000"),
            ("camera more than $500", "camera over $500"),
        ]
        
        for input_query, expected_output in test_cases:
            result = format_search_query_fallback(input_query)
            assert result == expected_output

    def test_fallback_formatter_removes_stop_words(self):
        """Test that fallback formatter removes common stop words."""
        test_cases = [
            ("a laptop with 16GB RAM", "laptop 16GB RAM"),
            ("the headphones for gaming", "headphones gaming"),
            ("phone by Apple", "phone Apple"),
        ]
        
        for input_query, expected_output in test_cases:
            result = format_search_query_fallback(input_query)
            assert result == expected_output

    def test_extract_parameters_price_constraints(self):
        """Test that parameter extraction correctly identifies price constraints."""
        # Under price
        params = extract_parameters_from_query("laptop under $500")
        assert params["max_price"] == 500.0
        assert params["min_price"] is None
        
        # Price range
        params = extract_parameters_from_query("headphones $20-$50")
        assert params["min_price"] == 20.0
        assert params["max_price"] == 50.0
        
        # Over price
        params = extract_parameters_from_query("phone over $300")
        assert params["min_price"] == 300.0
        assert params["max_price"] is None
        
        # No price constraints
        params = extract_parameters_from_query("wireless keyboard")
        assert params["min_price"] is None
        assert params["max_price"] is None

    def test_extract_parameters_brands(self):
        """Test that parameter extraction correctly identifies brands."""
        # Single brand
        params = extract_parameters_from_query("apple watch")
        assert "apple" in params["brands"]
        
        # Multiple brands
        params = extract_parameters_from_query("compare samsung and sony TVs")
        assert "samsung" in params["brands"]
        assert "sony" in params["brands"]
        
        # No brands
        params = extract_parameters_from_query("wireless keyboard")
        assert len(params["brands"]) == 0

    def test_extract_parameters_keywords(self):
        """Test that parameter extraction correctly identifies keywords."""
        params = extract_parameters_from_query("find me a gaming laptop with 16GB RAM")
        assert "gaming" in params["keywords"]
        assert "laptop" in params["keywords"]
        assert "16GB" in params["keywords"]
        assert "RAM" in params["keywords"]
        
        # Test that brands are not included in keywords
        params = extract_parameters_from_query("apple watch series 7")
        assert "watch" in params["keywords"]
        assert "series" in params["keywords"]
        assert "7" in params["keywords"]
        assert "apple" not in params["keywords"]  # Should be in brands, not keywords

    @pytest.mark.asyncio
    async def test_ai_formatter_calls_llm(self):
        """Test that AI formatter correctly calls the LLM."""
        # Create mock AI service
        mock_ai_service = MagicMock()
        mock_ai_service.llm = AsyncMock()
        mock_ai_service.llm.ainvoke.return_value = MagicMock(content="gaming laptop 16GB RAM")
        
        result = await format_search_query_with_ai(
            "I want to find a gaming laptop with 16GB RAM",
            "amazon",
            mock_ai_service
        )
        
        # Check that LLM was called
        mock_ai_service.llm.ainvoke.assert_called_once()
        
        # Check that result is processed correctly
        assert result == "gaming laptop 16GB RAM"
        
    @pytest.mark.asyncio
    async def test_ai_formatter_falls_back_on_error(self):
        """Test that AI formatter falls back to fallback formatter on error."""
        # Create mock AI service that raises an exception
        mock_ai_service = MagicMock()
        mock_ai_service.llm = AsyncMock()
        mock_ai_service.llm.ainvoke.side_effect = Exception("LLM error")
        
        result = await format_search_query_with_ai(
            "I want to find a gaming laptop with 16GB RAM",
            "amazon",
            mock_ai_service
        )
        
        # Check that result is from fallback formatter
        assert result == "gaming laptop 16GB RAM"
        
    @pytest.mark.asyncio
    async def test_ai_formatter_falls_back_when_ai_unavailable(self):
        """Test that AI formatter falls back when AI service is unavailable."""
        # None AI service
        result = await format_search_query_with_ai(
            "I want to find a gaming laptop with 16GB RAM",
            "amazon",
            None
        )
        
        # Check that result is from fallback formatter
        assert result == "gaming laptop 16GB RAM"
        
        # AI service without LLM
        mock_ai_service = MagicMock()
        mock_ai_service.llm = None
        
        result = await format_search_query_with_ai(
            "I want to find a gaming laptop with 16GB RAM",
            "amazon",
            mock_ai_service
        )
        
        # Check that result is from fallback formatter
        assert result == "gaming laptop 16GB RAM"
        
    @pytest.mark.asyncio
    async def test_optimized_query_with_ai(self):
        """Test that optimized query returns both formatted query and parameters."""
        # Create mock AI service
        mock_ai_service = MagicMock()
        mock_ai_service.llm = AsyncMock()
        mock_ai_service.llm.ainvoke.return_value = MagicMock(content="apple watch series 7")
        
        result = await get_optimized_query_for_marketplace(
            "I want to find an Apple Watch Series 7 under $300",
            "amazon",
            mock_ai_service
        )
        
        # Check that formatted query is from AI
        assert result["formatted_query"] == "apple watch series 7"
        
        # Check that parameters are extracted
        assert result["parameters"]["max_price"] == 300.0
        assert "apple" in result["parameters"]["brands"]
        assert "watch" in result["parameters"]["keywords"]
        assert "series" in result["parameters"]["keywords"]
        
    @pytest.mark.asyncio
    async def test_optimized_query_with_fallback(self):
        """Test that optimized query works with fallback when AI is unavailable."""
        result = await get_optimized_query_for_marketplace(
            "I want to find an Apple Watch Series 7 under $300",
            "amazon",
            None
        )
        
        # Check that formatted query is from fallback
        assert result["formatted_query"] == "Apple Watch Series 7 under $300"
        
        # Check that parameters are extracted
        assert result["parameters"]["max_price"] == 300.0
        assert "apple" in result["parameters"]["brands"]
        assert "watch" in result["parameters"]["keywords"]
        assert "series" in result["parameters"]["keywords"] 