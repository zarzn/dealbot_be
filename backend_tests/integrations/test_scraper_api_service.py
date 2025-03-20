"""Test ScraperAPIService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.integrations.scraper_api import ScraperAPIService
from core.models.enums import MarketType
from core.services.market_metrics import MarketMetricsService


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock()


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get.return_value = None
    return redis


@pytest.fixture
def mock_metrics_service():
    """Mock MarketMetricsService"""
    service = AsyncMock(spec=MarketMetricsService)
    service.record_market_request = AsyncMock(return_value=True)
    return service


class TestScraperAPIService:
    """Test ScraperAPIService"""

    @pytest.mark.asyncio
    @patch('core.integrations.scraper_api.MarketMetricsService')
    async def test_record_market_metrics(self, mock_metrics_service_class, mock_db):
        """Test _record_market_metrics method"""
        # Setup
        mock_metrics_instance = AsyncMock()
        mock_metrics_service_class.return_value = mock_metrics_instance
        
        service = ScraperAPIService(api_key="test_key", db=mock_db)
        
        # Execute
        await service._record_market_metrics(
            market_type=MarketType.AMAZON,
            success=True,
            response_time=1.5,
            error=None
        )
        
        # Assert
        mock_metrics_service_class.assert_called_once_with(mock_db)
        mock_metrics_instance.record_market_request.assert_called_once_with(
            market_type=MarketType.AMAZON,
            success=True,
            response_time=1.5,
            error=None
        )

    @pytest.mark.asyncio
    @patch('core.integrations.scraper_api.MarketMetricsService')
    async def test_record_market_metrics_no_db(self, mock_metrics_service_class):
        """Test _record_market_metrics method with no DB session"""
        # Setup
        service = ScraperAPIService(api_key="test_key", db=None)
        
        # Execute
        await service._record_market_metrics(
            market_type=MarketType.AMAZON,
            success=True,
            response_time=1.5,
            error=None
        )
        
        # Assert
        mock_metrics_service_class.assert_not_called()

    @pytest.mark.asyncio
    @patch('core.integrations.scraper_api.aiohttp.ClientSession')
    @patch('core.integrations.scraper_api.ScraperAPIService._record_market_metrics')
    async def test_search_amazon_records_metrics(self, mock_record_metrics, mock_session, mock_redis_client):
        """Test search_amazon records metrics"""
        # Setup
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = '{"results": []}'
        mock_response.json.return_value = {"results": []}
        
        mock_session_instance = AsyncMock()
        mock_session_instance.get.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value = mock_session_instance
        
        service = ScraperAPIService(api_key="test_key", redis_client=mock_redis_client)
        
        # Execute
        try:
            await service.search_amazon("test query")
        except Exception:
            # Ignore any exceptions from the actual search
            pass
            
        # Assert
        mock_record_metrics.assert_called()
        assert mock_record_metrics.call_args[1]["market_type"] == MarketType.AMAZON
        assert "success" in mock_record_metrics.call_args[1]
        assert "response_time" in mock_record_metrics.call_args[1]

    @pytest.mark.asyncio
    @patch('core.integrations.scraper_api.aiohttp.ClientSession')
    @patch('core.integrations.scraper_api.ScraperAPIService._record_market_metrics')
    async def test_search_walmart_records_metrics(self, mock_record_metrics, mock_session, mock_redis_client):
        """Test search_walmart_products records metrics"""
        # Setup
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = '{"items": []}'
        mock_response.json.return_value = {"items": []}
        
        mock_session_instance = AsyncMock()
        mock_session_instance.get.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value = mock_session_instance
        
        service = ScraperAPIService(api_key="test_key", redis_client=mock_redis_client)
        
        # Execute
        try:
            await service.search_walmart_products("test query")
        except Exception:
            # Ignore any exceptions from the actual search
            pass
            
        # Assert
        mock_record_metrics.assert_called()
        assert mock_record_metrics.call_args[1]["market_type"] == MarketType.WALMART
        assert "success" in mock_record_metrics.call_args[1]
        assert "response_time" in mock_record_metrics.call_args[1] 