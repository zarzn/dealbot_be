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
    ValidationError,
    NotFoundError,
    MarketError
)
from backend_tests.utils.markers import service_test, depends_on
from backend_tests.factories.market import MarketFactory

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
    analytics_data = {
        "total_products": 500,
        "active_deals": 50,
        "average_discount": 15.5,
        "top_categories": [
            {"name": "Electronics", "count": 120},
            {"name": "Home & Garden", "count": 80},
            {"name": "Clothing", "count": 60}
        ],
        "price_ranges": {
            "0-50": 100,
            "51-100": 150,
            "101-200": 120,
            "201+": 130
        },
        "daily_stats": {
            "views": 1200,
            "clicks": 500,
            "purchases": 50
        }
    }
    expected_analytics = MarketAnalytics(**analytics_data)
    mock_analytics_repository.get_market_analytics.return_value = analytics_data
    mock_market_repository = analytics_service.market_repository
    mock_market_repository.get_by_id.return_value = MagicMock()  # Make sure market exists
    
    # Execute
    result = await analytics_service.get_market_analytics(market_id)
    
    # Verify
    mock_analytics_repository.get_market_analytics.assert_called_once_with(market_id)
    assert result.total_products == 500
    assert result.active_deals == 50
    assert result.average_discount == 15.5

@service_test
async def test_get_market_analytics_not_found(analytics_service, mock_analytics_repository):
    """Test get_market_analytics when no analytics found."""
    # Setup
    market_id = uuid4()
    mock_analytics_repository.get_market_analytics.side_effect = NotFoundError(
        message="Market analytics not found",
        resource_type="MarketAnalytics",
        resource_id=str(market_id)
    )
    
    # Test and assertions
    with pytest.raises(MarketError):
        await analytics_service.get_market_analytics(market_id)
    
    mock_analytics_repository.get_market_analytics.assert_called_once_with(market_id)

@service_test
async def test_get_market_comparison(analytics_service, mock_analytics_repository):
    """Test getting market comparison."""
    # Setup
    market_id1 = uuid4()
    market_id2 = uuid4()
    metrics = ["total_products", "average_price"]
    comparison_data = {
        "comparison_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "markets": [
            {
                "id": str(market_id1),
                "name": "Amazon",
                "total_products": 1200,
                "average_price": 89.5
            },
            {
                "id": str(market_id2),
                "name": "eBay",
                "total_products": 950,
                "average_price": 75.3
            }
        ],
        "summary": {
            "best_overall": "Amazon",
            "best_prices": "eBay",
            "most_products": "Amazon",
            "fastest_delivery": "Amazon"
        }
    }
    expected_comparison = MarketComparison(**comparison_data)
    mock_analytics_repository.get_market_comparison.return_value = comparison_data
    mock_market_repository = analytics_service.market_repository
    mock_market_repository.get_by_id.return_value = MagicMock()  # Make sure market exists
    
    # Execute
    result = await analytics_service.get_market_comparison([market_id1, market_id2], metrics)
    
    # Verify
    mock_analytics_repository.get_market_comparison.assert_called_once_with([market_id1, market_id2], metrics)
    assert result.comparison_date == comparison_data["comparison_date"]
    assert len(result.markets) == 2
    assert result.markets[0]["id"] == str(market_id1)
    assert result.markets[1]["id"] == str(market_id2)

@service_test
async def test_get_market_price_history(analytics_service, mock_analytics_repository):
    """Test getting market price history."""
    # Setup
    market_id = uuid4()
    product_id = "product123"
    history_data = {
        "market_id": market_id,
        "product_id": product_id,
        "price_points": [
            {"date": "2023-01-01", "price": 99.99},
            {"date": "2023-01-15", "price": 89.99},
            {"date": "2023-02-01", "price": 79.99}
        ],
        "average_price": 89.99,
        "lowest_price": 79.99,
        "highest_price": 99.99,
        "price_trend": "decreasing"
    }
    expected_history = MarketPriceHistory(**history_data)
    mock_analytics_repository.get_price_history.return_value = history_data
    
    # Execute
    result = await analytics_service.get_market_price_history(market_id, product_id)
    
    # Verify
    mock_analytics_repository.get_price_history.assert_called_once_with(market_id, product_id, None, None)
    assert result.market_id == market_id
    assert result.product_id == product_id
    assert len(result.price_points) == 3
    assert result.price_trend == "decreasing"

@service_test
async def test_get_market_availability(analytics_service, mock_analytics_repository):
    """Test getting market availability."""
    # Setup
    market_id = uuid4()
    availability_data = {
        "market_id": market_id,
        "total_products": 1000,
        "available_products": 850,
        "out_of_stock": 150,
        "availability_rate": 0.85,
        "last_checked": datetime.utcnow()
    }
    expected_availability = MarketAvailability(**availability_data)
    mock_analytics_repository.get_market_availability.return_value = availability_data
    
    # Execute
    result = await analytics_service.get_market_availability(market_id)
    
    # Verify
    mock_analytics_repository.get_market_availability.assert_called_once_with(market_id)
    assert result.market_id == market_id
    assert result.total_products == 1000
    assert result.available_products == 850
    assert result.availability_rate == 0.85

@service_test
async def test_get_market_trends(analytics_service, mock_analytics_repository):
    """Test getting market trends."""
    # Setup
    market_id = uuid4()
    trend_period = "24h"  # Default value used in the service
    trends_data = {
        "trend_period": "30d",
        "top_trending": [
            {"name": "Smartphone", "growth": 25.5},
            {"name": "Tablet", "growth": 15.2},
            {"name": "Laptop", "growth": 10.1}
        ],
        "price_trends": {
            "Electronics": -5.2,
            "Home & Garden": 2.3,
            "Clothing": 0.5
        },
        "category_trends": [
            {"name": "Electronics", "change": 12.5},
            {"name": "Home & Garden", "change": 8.3},
            {"name": "Clothing", "change": -2.1}
        ],
        "search_trends": [
            {"count": 15000, "term": 1},  # Fixed: term is now an integer
            {"count": 12000, "term": 2},  # Fixed: term is now an integer
            {"count": 8000, "term": 3}    # Fixed: term is now an integer
        ]
    }
    expected_trends = MarketTrends(**trends_data)
    mock_analytics_repository.get_market_trends.return_value = trends_data
    mock_market_repository = analytics_service.market_repository
    mock_market_repository.get_by_id.return_value = MagicMock()  # Make sure market exists
    
    # Execute
    result = await analytics_service.get_market_trends(market_id, trend_period)
    
    # Verify
    mock_analytics_repository.get_market_trends.assert_called_once_with(market_id, trend_period)
    assert result.trend_period == "30d"
    assert len(result.top_trending) == 3
    assert len(result.category_trends) == 3
    assert len(result.search_trends) == 3

@service_test
async def test_get_market_performance(analytics_service, mock_analytics_repository):
    """Test getting market performance."""
    # Setup
    market_id = uuid4()
    performance_data = {
        "market_id": market_id,
        "uptime": 99.8,
        "response_times": {
            "avg": 0.35,
            "p50": 0.25,
            "p90": 0.5,
            "p99": 0.9
        },
        "error_rates": {
            "4xx": 0.2,
            "5xx": 0.5,
            "total": 0.7
        },
        "success_rates": {
            "searches": 99.5,
            "product_details": 99.8,
            "overall": 99.6
        },
        "api_usage": {
            "searches": 15000,
            "product_details": 25000,
            "price_checks": 10000
        }
    }
    expected_performance = MarketPerformance(**performance_data)
    mock_analytics_repository.get_market_performance.return_value = performance_data
    
    # Execute
    result = await analytics_service.get_market_performance(market_id)
    
    # Verify
    mock_analytics_repository.get_market_performance.assert_called_once_with(market_id)
    assert result.market_id == market_id
    assert result.uptime == 99.8
    assert "avg" in result.response_times
    assert "searches" in result.success_rates

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
    with pytest.raises(MarketError):
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
    with pytest.raises(MarketError):
        await analytics_service.aggregate_market_stats(market_id)
    
    mock_analytics_repository.aggregate_market_stats.assert_called_once_with(market_id)
    mock_logger.error.assert_called()

@service_test
async def test_get_deal_analysis(analytics_service, mock_analytics_repository):
    """Test getting deal analysis."""
    # Setup
    deal_id = uuid4()
    user_id = uuid4()
    
    # Mock repository to return None for get_deal_analysis (no cached analysis)
    mock_analytics_repository.get_deal_analysis.return_value = None
    
    # Mock the deal repository to return a deal
    mock_deal = MagicMock()
    mock_deal.id = deal_id
    mock_deal.price = 100.0
    mock_deal.original_price = 150.0
    mock_deal.seller_info = {"rating": 4.5}  # Add seller_info dictionary with rating
    mock_deal.expires_at = None  # No expiration date
    mock_deal.is_available = True  # Deal is available
    analytics_service.deal_repository.get_by_id.return_value = mock_deal
    
    # Mock the repository's save_deal_analysis method to do nothing
    mock_analytics_repository.save_deal_analysis = AsyncMock()
    
    # Mock the deal analysis service
    mock_deal_analysis_service = AsyncMock()
    # We're not actually calling generate_simplified_analysis, so we don't need to mock its return value
    
    # Execute
    result = await analytics_service.get_deal_analysis(
        deal_id, 
        user_id,
        deal_analysis_service=mock_deal_analysis_service
    )
    
    # Verify the result is an AIAnalysis object with expected attributes
    assert isinstance(result, AIAnalysis)
    assert result.deal_id == deal_id
    assert 0 <= result.score <= 1.0  # Score should be normalized between 0 and 1
    assert 0 <= result.confidence <= 1.0  # Confidence should be between 0 and 1
    assert isinstance(result.price_analysis, dict)
    assert isinstance(result.market_analysis, dict)
    assert isinstance(result.recommendations, list)
    assert len(result.recommendations) > 0  # Should have at least one recommendation

@service_test
async def test_get_deal_analysis_not_found(analytics_service, mock_analytics_repository):
    """Test get_deal_analysis when no analysis found."""
    # Setup
    deal_id = uuid4()
    mock_analytics_repository.get_deal_analysis.side_effect = NotFoundError(
        message="Deal analysis not found",
        resource_type="AIAnalysis",
        resource_id=str(deal_id)
    )
    
    # Test and assertions
    with pytest.raises(NotFoundError):
        await analytics_service.get_deal_analysis(deal_id)
    
    mock_analytics_repository.get_deal_analysis.assert_called_once_with(deal_id) 