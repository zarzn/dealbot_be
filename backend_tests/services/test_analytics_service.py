"""Tests for Analytics Service.

This module contains tests for the AnalyticsService class.
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from core.services.analytics import AnalyticsService
from core.repositories.analytics import AnalyticsRepository
from core.repositories.market import MarketRepository
from core.repositories.deal import DealRepository
from core.models.market import (
    MarketAnalytics,
    MarketComparison,
    MarketPriceHistory,
    MarketAvailability,
    MarketTrends,
    MarketPerformance
)
from core.models.deal import AIAnalysis
from core.exceptions import (
    NotFoundException,
    AnalyticsError,
    ValidationError
)
from utils.markers import service_test, depends_on
from factories.market import MarketFactory

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def mock_analytics_repository():
    """Create a mock analytics repository for testing."""
    return AsyncMock(spec=AnalyticsRepository)

@pytest.fixture
async def mock_market_repository():
    """Create a mock market repository for testing."""
    return AsyncMock(spec=MarketRepository)

@pytest.fixture
async def mock_deal_repository():
    """Create a mock deal repository for testing."""
    return AsyncMock(spec=DealRepository)

@pytest.fixture
async def analytics_service(
    mock_analytics_repository,
    mock_market_repository,
    mock_deal_repository
):
    """Create an analytics service with mock repositories for testing."""
    return AnalyticsService(
        analytics_repository=mock_analytics_repository,
        market_repository=mock_market_repository,
        deal_repository=mock_deal_repository
    )

@service_test
async def test_get_market_analytics(analytics_service, mock_analytics_repository):
    """Test getting market analytics."""
    # Setup
    market_id = uuid4()
    expected_analytics = MarketAnalytics(
        market_id=market_id,
        volume_24h=1000.0,
        change_24h=5.2,
        average_price=120.5,
        highest_price=150.0,
        lowest_price=100.0,
        total_trades=50,
        generated_at=datetime.utcnow()
    )
    mock_analytics_repository.get_market_analytics.return_value = expected_analytics
    
    # Execute
    result = await analytics_service.get_market_analytics(market_id)
    
    # Verify
    mock_analytics_repository.get_market_analytics.assert_called_once_with(market_id)
    assert result == expected_analytics
    assert result.market_id == market_id
    assert result.volume_24h == 1000.0
    assert result.change_24h == 5.2

@service_test
async def test_get_market_analytics_not_found(analytics_service, mock_analytics_repository):
    """Test getting market analytics when not found."""
    # Setup
    market_id = uuid4()
    mock_analytics_repository.get_market_analytics.side_effect = NotFoundException(f"No analytics found for market {market_id}")
    
    # Execute and verify
    with pytest.raises(NotFoundException):
        await analytics_service.get_market_analytics(market_id)
    
    mock_analytics_repository.get_market_analytics.assert_called_once_with(market_id)

@service_test
async def test_get_market_comparison(analytics_service, mock_analytics_repository):
    """Test getting market comparison."""
    # Setup
    market_ids = [uuid4(), uuid4()]
    metrics = ["volume_24h", "change_24h"]
    expected_comparison = MarketComparison(
        markets=market_ids,
        metrics=metrics,
        data={
            str(market_ids[0]): {"volume_24h": 1000.0, "change_24h": 5.2},
            str(market_ids[1]): {"volume_24h": 2000.0, "change_24h": -1.5}
        },
        generated_at=datetime.utcnow()
    )
    mock_analytics_repository.get_market_comparison.return_value = expected_comparison
    
    # Execute
    result = await analytics_service.get_market_comparison(market_ids, metrics)
    
    # Verify
    mock_analytics_repository.get_market_comparison.assert_called_once_with(market_ids, metrics)
    assert result == expected_comparison
    assert len(result.markets) == 2
    assert result.metrics == metrics
    assert str(market_ids[0]) in result.data
    assert str(market_ids[1]) in result.data

@service_test
async def test_get_market_price_history(analytics_service, mock_analytics_repository):
    """Test getting market price history."""
    # Setup
    market_id = uuid4()
    product_id = "BTC-USD"
    start_date = datetime.utcnow() - timedelta(days=7)
    end_date = datetime.utcnow()
    
    price_points = [
        {"timestamp": start_date + timedelta(hours=i), "price": 100.0 + i}
        for i in range(0, 168, 6)  # Every 6 hours for a week
    ]
    
    expected_history = MarketPriceHistory(
        market_id=market_id,
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
        interval="6h",
        price_points=price_points,
        generated_at=datetime.utcnow()
    )
    mock_analytics_repository.get_market_price_history.return_value = expected_history
    
    # Execute
    result = await analytics_service.get_market_price_history(
        market_id, 
        product_id, 
        start_date, 
        end_date
    )
    
    # Verify
    mock_analytics_repository.get_market_price_history.assert_called_once_with(
        market_id, 
        product_id, 
        start_date, 
        end_date
    )
    assert result == expected_history
    assert result.market_id == market_id
    assert result.product_id == product_id
    assert result.start_date == start_date
    assert result.end_date == end_date
    assert len(result.price_points) > 0

@service_test
async def test_get_market_availability(analytics_service, mock_analytics_repository):
    """Test getting market availability."""
    # Setup
    market_id = uuid4()
    expected_availability = MarketAvailability(
        market_id=market_id,
        is_available=True,
        uptime_percentage=99.8,
        last_checked=datetime.utcnow(),
        generated_at=datetime.utcnow()
    )
    mock_analytics_repository.get_market_availability.return_value = expected_availability
    
    # Execute
    result = await analytics_service.get_market_availability(market_id)
    
    # Verify
    mock_analytics_repository.get_market_availability.assert_called_once_with(market_id)
    assert result == expected_availability
    assert result.market_id == market_id
    assert result.is_available is True
    assert result.uptime_percentage == 99.8

@service_test
async def test_get_market_trends(analytics_service, mock_analytics_repository):
    """Test getting market trends."""
    # Setup
    market_id = uuid4()
    trend_period = "24h"
    expected_trends = MarketTrends(
        market_id=market_id,
        period=trend_period,
        direction="up",
        strength=0.75,
        indicators={
            "moving_average": "bullish",
            "relative_strength": "overbought",
            "volume": "increasing"
        },
        generated_at=datetime.utcnow()
    )
    mock_analytics_repository.get_market_trends.return_value = expected_trends
    
    # Execute
    result = await analytics_service.get_market_trends(market_id, trend_period)
    
    # Verify
    mock_analytics_repository.get_market_trends.assert_called_once_with(market_id, trend_period)
    assert result == expected_trends
    assert result.market_id == market_id
    assert result.period == trend_period
    assert result.direction == "up"
    assert result.strength == 0.75
    assert "moving_average" in result.indicators

@service_test
async def test_get_market_performance(analytics_service, mock_analytics_repository):
    """Test getting market performance."""
    # Setup
    market_id = uuid4()
    expected_performance = MarketPerformance(
        market_id=market_id,
        score=85.5,
        liquidity_rating="high",
        volatility_rating="medium",
        reliability_rating="high",
        generated_at=datetime.utcnow()
    )
    mock_analytics_repository.get_market_performance.return_value = expected_performance
    
    # Execute
    result = await analytics_service.get_market_performance(market_id)
    
    # Verify
    mock_analytics_repository.get_market_performance.assert_called_once_with(market_id)
    assert result == expected_performance
    assert result.market_id == market_id
    assert result.score == 85.5
    assert result.liquidity_rating == "high"
    assert result.volatility_rating == "medium"
    assert result.reliability_rating == "high"

@service_test
async def test_update_market_analytics(analytics_service, mock_analytics_repository):
    """Test updating market analytics."""
    # Setup
    market_id = uuid4()
    analytics_data = {
        "volume_24h": 1500.0,
        "change_24h": 2.5,
        "average_price": 125.0
    }
    
    # Execute
    await analytics_service.update_market_analytics(market_id, analytics_data)
    
    # Verify
    mock_analytics_repository.update_market_analytics.assert_called_once_with(market_id, analytics_data)

@service_test
async def test_update_market_analytics_validation_error(analytics_service, mock_analytics_repository):
    """Test updating market analytics with invalid data."""
    # Setup
    market_id = uuid4()
    invalid_data = {
        "volume_24h": -100.0,  # Negative volume is invalid
        "change_24h": 2.5
    }
    mock_analytics_repository.update_market_analytics.side_effect = ValidationError("Volume cannot be negative")
    
    # Execute and verify
    with pytest.raises(ValidationError):
        await analytics_service.update_market_analytics(market_id, invalid_data)
    
    mock_analytics_repository.update_market_analytics.assert_called_once_with(market_id, invalid_data)

@service_test
async def test_aggregate_market_stats(analytics_service, mock_analytics_repository):
    """Test aggregating market stats."""
    # Setup
    market_id = uuid4()
    
    # Execute
    await analytics_service.aggregate_market_stats(market_id)
    
    # Verify
    mock_analytics_repository.aggregate_market_stats.assert_called_once_with(market_id)

@service_test
@patch("core.services.analytics.logger")
async def test_aggregate_market_stats_error(
    mock_logger, 
    analytics_service, 
    mock_analytics_repository
):
    """Test error handling during market stats aggregation."""
    # Setup
    market_id = uuid4()
    mock_analytics_repository.aggregate_market_stats.side_effect = AnalyticsError("Failed to aggregate stats")
    
    # Execute and verify
    with pytest.raises(AnalyticsError):
        await analytics_service.aggregate_market_stats(market_id)
    
    mock_analytics_repository.aggregate_market_stats.assert_called_once_with(market_id)
    mock_logger.error.assert_called()

@service_test
async def test_get_deal_analysis(analytics_service, mock_analytics_repository):
    """Test getting deal analysis."""
    # Setup
    deal_id = uuid4()
    user_id = uuid4()
    
    mock_deal_analysis_service = AsyncMock()
    mock_deal_analysis_service.analyze_deal.return_value = AIAnalysis(
        deal_id=deal_id,
        risk_score=65,
        confidence=0.85,
        analysis_text="This is a moderate risk deal with good potential returns.",
        recommendation="Buy",
        strengths=["Strong market position", "Growing sector"],
        weaknesses=["Regulatory uncertainty", "Volatile pricing"],
        generated_at=datetime.utcnow()
    )
    
    # Execute
    result = await analytics_service.get_deal_analysis(
        deal_id, 
        user_id,
        deal_analysis_service=mock_deal_analysis_service
    )
    
    # Verify
    mock_deal_analysis_service.analyze_deal.assert_called_once_with(deal_id, user_id)
    assert result.deal_id == deal_id
    assert result.risk_score == 65
    assert result.confidence == 0.85
    assert "moderate risk" in result.analysis_text
    assert result.recommendation == "Buy"
    assert len(result.strengths) == 2
    assert len(result.weaknesses) == 2

@service_test
async def test_get_deal_analysis_not_found(analytics_service, mock_analytics_repository):
    """Test getting deal analysis when deal not found."""
    # Setup
    deal_id = uuid4()
    user_id = uuid4()
    
    mock_deal_analysis_service = AsyncMock()
    mock_deal_analysis_service.analyze_deal.side_effect = NotFoundException(f"Deal {deal_id} not found")
    
    # Execute and verify
    with pytest.raises(NotFoundException):
        await analytics_service.get_deal_analysis(
            deal_id, 
            user_id,
            deal_analysis_service=mock_deal_analysis_service
        )
    
    mock_deal_analysis_service.analyze_deal.assert_called_once_with(deal_id, user_id) 