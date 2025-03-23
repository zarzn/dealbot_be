"""
Unit tests for the deal search monitoring module.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
import uuid

from core.services.deal.search.monitoring import (
    monitor_deals,
    fetch_deals_from_api,
    build_search_params,
    process_and_store_deals,
    check_expired_deals
)
from core.models.deal import DealStatus


class TestDealMonitoring:
    """Tests for the deal monitoring module."""
    
    @pytest.mark.asyncio
    async def test_monitor_deals(self):
        """Test the monitor_deals function."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        mock_instance._repository = AsyncMock()
        mock_instance._repository.get_active_goals = AsyncMock(return_value=[
            {"id": str(uuid4()), "category": "electronics", "keywords": ["laptop"]}
        ])
        mock_instance._fetch_deals_from_api = AsyncMock(return_value=[])
        mock_instance.amazon_api = AsyncMock()
        mock_instance.walmart_api = AsyncMock()
        mock_instance._process_and_store_deals = AsyncMock()
        mock_instance.check_expired_deals = AsyncMock()
        
        # Call the function
        await monitor_deals(mock_instance)
        
        # Verify that repository method was called
        mock_instance._repository.get_active_goals.assert_called_once()
        
        # Verify that _fetch_deals_from_api was called with APIs
        assert mock_instance._fetch_deals_from_api.call_count == 2
        
        # Verify that check_expired_deals was called
        mock_instance.check_expired_deals.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_deals_with_deals(self):
        """Test monitor_deals function when deals are found."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        mock_instance._repository = AsyncMock()
        mock_instance._repository.get_active_goals = AsyncMock(return_value=[
            {"id": str(uuid4()), "category": "electronics", "keywords": ["laptop"]}
        ])
        
        # Mock finding deals
        mock_instance._fetch_deals_from_api = AsyncMock()
        mock_instance._fetch_deals_from_api.side_effect = [
            [{"id": "1", "title": "Deal 1"}],  # Amazon deals
            [{"id": "2", "title": "Deal 2"}]   # Walmart deals
        ]
        
        mock_instance.amazon_api = AsyncMock()
        mock_instance.walmart_api = AsyncMock()
        mock_instance._process_and_store_deals = AsyncMock()
        mock_instance.check_expired_deals = AsyncMock()
        
        # Call the function
        await monitor_deals(mock_instance)
        
        # Verify that process_and_store_deals was called with all deals
        mock_instance._process_and_store_deals.assert_called_once()
        call_args = mock_instance._process_and_store_deals.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0]["id"] == "1"
        assert call_args[1]["id"] == "2"
    
    @pytest.mark.asyncio
    async def test_monitor_deals_with_api_error(self):
        """Test monitor_deals function when APIs return errors."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        mock_instance._repository = AsyncMock()
        mock_instance._repository.get_active_goals = AsyncMock(return_value=[
            {"id": str(uuid4()), "category": "electronics", "keywords": ["laptop"]}
        ])
        
        # Mock API error
        mock_instance._fetch_deals_from_api = AsyncMock(side_effect=Exception("API Error"))
        mock_instance.amazon_api = AsyncMock()
        mock_instance.walmart_api = AsyncMock()
        mock_instance._process_and_store_deals = AsyncMock()
        mock_instance.check_expired_deals = AsyncMock()
        
        # Add crawler for fallback
        mock_instance.crawler = AsyncMock()
        mock_instance.crawler.scrape_fallback = AsyncMock(return_value=[
            {"id": "3", "title": "Deal 3"}
        ])
        
        # Call the function
        await monitor_deals(mock_instance)
        
        # Verify that crawler was called
        mock_instance.crawler.scrape_fallback.assert_called_once_with("electronics")
        
        # Verify that process_and_store_deals was called with scraped deals
        mock_instance._process_and_store_deals.assert_called_once()
        call_args = mock_instance._process_and_store_deals.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["id"] == "3"
    
    @pytest.mark.asyncio
    async def test_fetch_deals_from_api(self):
        """Test fetching deals from e-commerce API."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        mock_instance._build_search_params = MagicMock(return_value={
            "keywords": ["laptop"],
            "price_range": (500, 1000)
        })
        
        # Mock API
        mock_api = AsyncMock()
        mock_api.search_deals = AsyncMock()
        mock_api.search_deals.side_effect = [
            [{"id": "1", "title": "Deal 1"}],
            [{"id": "2", "title": "Deal 2"}]
        ]
        
        # Test with multiple goals
        goals = [
            {"id": "goal1", "keywords": ["laptop"]},
            {"id": "goal2", "keywords": ["tablet"]}
        ]
        
        # Call the function
        result = await fetch_deals_from_api(mock_instance, mock_api, goals)
        
        # Verify API was called for each goal
        assert mock_api.search_deals.call_count == 2
        
        # Verify results were collected
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"
    
    def test_build_search_params(self):
        """Test building search parameters from goal constraints."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        
        # Test with full goal data
        goal = {
            "keywords": ["laptop", "gaming"],
            "min_price": 500,
            "max_price": 1500,
            "brands": ["Dell", "Alienware"],
            "categories": ["electronics", "computers"]
        }
        
        result = build_search_params(mock_instance, goal)
        
        # Verify parameters were built correctly
        assert result["keywords"] == ["laptop", "gaming"]
        assert result["price_range"] == (500, 1500)
        assert result["brands"] == ["Dell", "Alienware"]
        assert result["categories"] == ["electronics", "computers"]
        
        # Test with partial goal data
        goal = {
            "keywords": ["laptop"]
        }
        
        result = build_search_params(mock_instance, goal)
        
        # Verify parameters were built with defaults
        assert result["keywords"] == ["laptop"]
        assert result["price_range"] == (None, None)
        assert result["brands"] == []
        assert result["categories"] == []
    
    @pytest.mark.asyncio
    async def test_process_and_store_deals(self):
        """Test processing and storing fetched deals."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        mock_instance.create_deal = AsyncMock()
        
        # Create test deals
        deals = [
            {
                "user_id": str(uuid4()),
                "goal_id": str(uuid4()),
                "market_id": str(uuid4()),
                "product_name": "Gaming Laptop",
                "price": 999.99,
                "currency": "USD",
                "url": "https://example.com/product",
                "description": "Powerful gaming laptop",
                "original_price": 1299.99,
                "source": "amazon",
                "image_url": "https://example.com/image.jpg",
                "expires_at": datetime.utcnow() + timedelta(days=7),
                "metadata": {"brand": "Dell"}
            },
            {
                "user_id": str(uuid4()),
                "goal_id": str(uuid4()),
                "market_id": str(uuid4()),
                "title": "Gaming Mouse",
                "price": 49.99,
                "currency": "USD",
                "url": "https://example.com/mouse",
                "source": "walmart"
            }
        ]
        
        # Call the function
        await process_and_store_deals(mock_instance, deals)
        
        # Verify create_deal was called for each deal
        assert mock_instance.create_deal.call_count == 2
        
        # Verify first call had all parameters
        first_call_kwargs = mock_instance.create_deal.call_args_list[0][1]
        assert first_call_kwargs["user_id"] == deals[0]["user_id"]
        assert first_call_kwargs["goal_id"] == deals[0]["goal_id"]
        assert first_call_kwargs["title"] == "Gaming Laptop"
        assert first_call_kwargs["price"] == 999.99
        assert first_call_kwargs["source"] == "amazon"
        assert first_call_kwargs["deal_metadata"] == {"brand": "Dell"}
        
        # Verify second call handled missing fields
        second_call_kwargs = mock_instance.create_deal.call_args_list[1][1]
        assert second_call_kwargs["title"] == "Gaming Mouse"
        assert "description" in second_call_kwargs
        assert second_call_kwargs["description"] is None
    
    @pytest.mark.asyncio
    async def test_process_and_store_deals_with_error(self):
        """Test processing deals with an error for one deal."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        mock_instance.create_deal = AsyncMock()
        mock_instance.create_deal.side_effect = [
            None,  # First call succeeds
            Exception("Failed to create deal")  # Second call raises exception
        ]
        
        # Create test deals
        deals = [
            {
                "user_id": str(uuid4()),
                "goal_id": str(uuid4()),
                "market_id": str(uuid4()),
                "product_name": "Gaming Laptop",
                "price": 999.99,
                "currency": "USD",
                "url": "https://example.com/product"
            },
            {
                "user_id": str(uuid4()),
                "goal_id": str(uuid4()),
                "market_id": str(uuid4()),
                "title": "Gaming Mouse",
                "price": 49.99,
                "currency": "USD",
                "url": "https://example.com/mouse"
            }
        ]
        
        # Call the function (should not raise exception)
        await process_and_store_deals(mock_instance, deals)
        
        # Verify create_deal was called for each deal
        assert mock_instance.create_deal.call_count == 2
    
    @pytest.mark.asyncio
    async def test_check_expired_deals(self):
        """Test checking for expired deals."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        mock_instance.db = AsyncMock()
        mock_instance.db.execute = AsyncMock()
        mock_instance.db.flush = AsyncMock()
        mock_instance.db.commit = AsyncMock()
        
        # Mock expired deals
        expired_deal1 = MagicMock()
        expired_deal1._status = DealStatus.ACTIVE.value.lower()
        
        expired_deal2 = MagicMock()
        expired_deal2._status = DealStatus.ACTIVE.value.lower()
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock())
        mock_result.scalars().all = MagicMock(return_value=[expired_deal1, expired_deal2])
        mock_instance.db.execute.return_value = mock_result
        
        # Mock notification method
        mock_instance.notify_deal_expired = AsyncMock()
        
        # Call the function
        await check_expired_deals(mock_instance)
        
        # Verify database was queried
        assert mock_instance.db.execute.call_count == 1
        
        # Verify deals were updated
        assert expired_deal1._status == DealStatus.EXPIRED.value.lower()
        assert expired_deal2._status == DealStatus.EXPIRED.value.lower()
        
        # Verify flush and commit were called
        assert mock_instance.db.flush.call_count == 2
        mock_instance.db.commit.assert_called_once()
        
        # Verify notifications were sent
        assert mock_instance.notify_deal_expired.call_count == 2
    
    @pytest.mark.asyncio
    async def test_check_expired_deals_no_expired(self):
        """Test checking for expired deals when none are found."""
        # Create a mock instance for 'self'
        mock_instance = MagicMock()
        mock_instance.db = AsyncMock()
        mock_instance.db.execute = AsyncMock()
        
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=MagicMock())
        mock_result.scalars().all = MagicMock(return_value=[])
        mock_instance.db.execute.return_value = mock_result
        
        # Call the function
        await check_expired_deals(mock_instance)
        
        # Verify database was queried
        assert mock_instance.db.execute.call_count == 1
        
        # Verify commit was not called since no updates
        assert not mock_instance.db.commit.called


# Helper function for tests
def uuid4():
    """Generate a random UUID4 string."""
    return str(uuid.uuid4()) 