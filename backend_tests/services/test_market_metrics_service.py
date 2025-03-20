"""Test market metrics service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.services.market_metrics import MarketMetricsService
from core.models.enums import MarketType
from core.repositories.market import MarketRepository


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_market_repository(mock_db):
    """Mock market repository"""
    repository = AsyncMock(spec=MarketRepository)
    repository.db = mock_db
    return repository


@pytest.fixture
def mock_market():
    """Mock market"""
    market = AsyncMock()
    market.id = "1234"
    market.record_request = AsyncMock()
    return market


class TestMarketMetricsService:
    """Test market metrics service"""

    @pytest.mark.asyncio
    async def test_record_market_request_success(self, mock_db, mock_market_repository, mock_market):
        """Test record_market_request with successful request"""
        # Setup
        mock_market_repository.get_by_type.return_value = [mock_market]
        service = MarketMetricsService(mock_db)
        service.market_repository = mock_market_repository

        # Execute
        result = await service.record_market_request(
            market_type=MarketType.AMAZON,
            success=True,
            response_time=1.23,
            error=None
        )

        # Assert
        mock_market_repository.get_by_type.assert_called_once_with(MarketType.AMAZON)
        mock_market.record_request.assert_called_once_with(
            db=mock_db,
            success=True,
            response_time=1.23,
            error=None
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_record_market_request_market_not_found(self, mock_db, mock_market_repository):
        """Test record_market_request when market not found"""
        # Setup
        mock_market_repository.get_by_type.return_value = []
        service = MarketMetricsService(mock_db)
        service.market_repository = mock_market_repository

        # Execute
        result = await service.record_market_request(
            market_type=MarketType.AMAZON,
            success=True,
            response_time=1.23,
            error=None
        )

        # Assert
        mock_market_repository.get_by_type.assert_called_once_with(MarketType.AMAZON)
        assert result is False

    @pytest.mark.asyncio
    async def test_record_market_request_exception(self, mock_db, mock_market_repository, mock_market):
        """Test record_market_request with exception"""
        # Setup
        mock_market_repository.get_by_type.return_value = [mock_market]
        mock_market.record_request.side_effect = Exception("Test exception")
        service = MarketMetricsService(mock_db)
        service.market_repository = mock_market_repository

        # Execute
        result = await service.record_market_request(
            market_type=MarketType.AMAZON,
            success=True,
            response_time=1.23,
            error=None
        )

        # Assert
        mock_market_repository.get_by_type.assert_called_once_with(MarketType.AMAZON)
        mock_market.record_request.assert_called_once_with(
            db=mock_db,
            success=True,
            response_time=1.23,
            error=None
        )
        assert result is False 