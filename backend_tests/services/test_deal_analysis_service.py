"""Tests for Deal Analysis Service.

This module contains tests for the DealAnalysisService class.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from decimal import Decimal

from core.services.deal_analysis import DealAnalysisService, AnalysisResult
from core.models.deal import Deal, DealStatus, DealPriority, AIAnalysis
from core.models.goal import Goal, GoalStatus
from core.exceptions import (
    DealError,
    DealAnalysisError,
    DataQualityError,
    APIServiceUnavailableError,
    ValidationError
)
from utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_price_history():
    """Create mock price history data."""
    dates = pd.date_range(
        start=datetime.utcnow() - timedelta(days=30),
        end=datetime.utcnow(),
        freq='D'
    )
    
    # Create sample price data with some trend
    prices = np.linspace(100, 120, len(dates)) + np.random.normal(0, 5, len(dates))
    volumes = np.random.randint(1000, 5000, len(dates))
    
    df = pd.DataFrame({
        'date': dates,
        'price': prices,
        'volume': volumes
    })
    
    return df

@pytest.fixture
def mock_similar_deals():
    """Create mock similar deals data."""
    return [
        {
            'id': str(uuid4()),
            'price': 110.5,
            'market_cap': 1_000_000,
            'volume': 5000,
            'score': 85,
            'features': ['feature1', 'feature2'],
            'status': 'completed',
            'created_at': (datetime.utcnow() - timedelta(days=5)).isoformat(),
            'completed_at': (datetime.utcnow() - timedelta(days=2)).isoformat()
        },
        {
            'id': str(uuid4()),
            'price': 105.2,
            'market_cap': 950_000,
            'volume': 4500,
            'score': 78,
            'features': ['feature1', 'feature3'],
            'status': 'completed',
            'created_at': (datetime.utcnow() - timedelta(days=10)).isoformat(),
            'completed_at': (datetime.utcnow() - timedelta(days=7)).isoformat()
        },
        {
            'id': str(uuid4()),
            'price': 115.8,
            'market_cap': 1_100_000,
            'volume': 5500,
            'score': 92,
            'features': ['feature2', 'feature3'],
            'status': 'completed',
            'created_at': (datetime.utcnow() - timedelta(days=15)).isoformat(),
            'completed_at': (datetime.utcnow() - timedelta(days=12)).isoformat()
        }
    ]

@pytest.fixture
def mock_deal():
    """Create a mock deal for testing."""
    return Mock(spec=Deal, 
        id=uuid4(),
        title="Test Deal",
        description="A test deal for analysis",
        price=Decimal('110.50'),
        market_cap=Decimal('1000000'),
        volume=Decimal('5000'),
        status=DealStatus.ACTIVE,
        priority=DealPriority.MEDIUM,
        features=['feature1', 'feature2'],
        created_at=datetime.utcnow() - timedelta(days=3),
        updated_at=datetime.utcnow(),
        market_id=uuid4(),
        user_id=uuid4(),
        metrics={
            'volatility': 0.15,
            'liquidity': 0.75,
            'growth': 0.5
        }
    )

@pytest.fixture
def mock_goal():
    """Create a mock goal for testing."""
    return Mock(spec=Goal,
        id=uuid4(),
        title="Test Goal",
        description="A test goal for analysis",
        status=GoalStatus.ACTIVE,
        target_metrics={
            'price_range': [100, 120],
            'market_cap_min': 900000,
            'features': ['feature1', 'feature2', 'feature3']
        },
        user_id=uuid4(),
        created_at=datetime.utcnow() - timedelta(days=10),
        updated_at=datetime.utcnow()
    )

@pytest.fixture
async def mock_market_service():
    """Create a mock market service."""
    mock_service = AsyncMock()
    mock_service.get_historical_prices.return_value = pd.DataFrame()
    return mock_service

@pytest.fixture
async def mock_deal_service():
    """Create a mock deal service."""
    mock_service = AsyncMock()
    mock_service.get_similar_deals.return_value = []
    return mock_service

@pytest.fixture
async def deal_analysis_service(
    mock_market_service,
    mock_deal_service,
    db_session
):
    """Create a deal analysis service with mock dependencies."""
    service = DealAnalysisService(
        session=db_session,
        market_service=mock_market_service,
        deal_service=mock_deal_service
    )
    
    # Patch some methods to avoid external dependencies
    service._get_similar_deals_with_retry = AsyncMock()
    service._cache_analysis = AsyncMock()
    
    return service

@service_test
async def test_analyze_deal(
    deal_analysis_service,
    mock_deal,
    mock_goal,
    mock_price_history,
    mock_similar_deals,
    mock_market_service,
    mock_deal_service
):
    """Test analyzing a deal."""
    # Setup
    deal_analysis_service._get_similar_deals_with_retry.return_value = mock_similar_deals
    mock_market_service.get_historical_prices.return_value = mock_price_history
    
    # Override some internal methods to control test behavior
    with patch.object(deal_analysis_service, '_analyze_price', return_value={'price_value': 0.85, 'trend': 0.75}), \
         patch.object(deal_analysis_service, '_analyze_historical_data', return_value={'volatility': 0.25, 'consistency': 0.8}), \
         patch.object(deal_analysis_service, '_analyze_market_data', return_value={'market_strength': 0.7, 'competition': 0.6}), \
         patch.object(deal_analysis_service, '_analyze_goal_fit', return_value={'feature_match': 0.9, 'target_match': 0.85}), \
         patch.object(deal_analysis_service, '_detect_anomalies', return_value=0.15), \
         patch.object(deal_analysis_service, '_generate_recommendations', return_value=["Consider buying", "Watch market trends"]):
        
        # Execute
        result = await deal_analysis_service.analyze_deal(mock_deal, mock_goal, mock_similar_deals)
        
        # Verify
        assert isinstance(result, AnalysisResult)
        assert result.deal_id == str(mock_deal.id)
        assert 0 <= result.score <= 100
        assert 0 <= result.confidence <= 1
        assert result.anomaly_score == 0.15
        assert len(result.recommendations) == 2
        assert "Consider buying" in result.recommendations
        assert "price" in result.metrics
        assert "historical" in result.metrics
        assert "market" in result.metrics
        assert "goal_fit" in result.metrics
        
        # Verify method calls
        deal_analysis_service._get_similar_deals_with_retry.assert_not_called()  # We passed similar_deals directly
        mock_market_service.get_historical_prices.assert_called_once()
        deal_analysis_service._cache_analysis.assert_called_once()

@service_test
async def test_analyze_deal_fetch_similar(
    deal_analysis_service,
    mock_deal,
    mock_goal,
    mock_price_history,
    mock_similar_deals,
    mock_market_service
):
    """Test analyzing a deal when similar deals need to be fetched."""
    # Setup
    deal_analysis_service._get_similar_deals_with_retry.return_value = mock_similar_deals
    mock_market_service.get_historical_prices.return_value = mock_price_history
    
    # Override some internal methods to control test behavior
    with patch.object(deal_analysis_service, '_analyze_price', return_value={'price_value': 0.85, 'trend': 0.75}), \
         patch.object(deal_analysis_service, '_analyze_historical_data', return_value={'volatility': 0.25, 'consistency': 0.8}), \
         patch.object(deal_analysis_service, '_analyze_market_data', return_value={'market_strength': 0.7, 'competition': 0.6}), \
         patch.object(deal_analysis_service, '_analyze_goal_fit', return_value={'feature_match': 0.9, 'target_match': 0.85}), \
         patch.object(deal_analysis_service, '_detect_anomalies', return_value=0.15), \
         patch.object(deal_analysis_service, '_generate_recommendations', return_value=["Consider buying", "Watch market trends"]):
        
        # Execute - without passing similar_deals
        result = await deal_analysis_service.analyze_deal(mock_deal, mock_goal)
        
        # Verify
        assert isinstance(result, AnalysisResult)
        assert result.deal_id == str(mock_deal.id)
        
        # Verify method calls
        deal_analysis_service._get_similar_deals_with_retry.assert_called_once_with(mock_deal)
        mock_market_service.get_historical_prices.assert_called_once()

@service_test
async def test_analyze_deal_error_handling(
    deal_analysis_service,
    mock_deal,
    mock_goal,
    mock_market_service
):
    """Test error handling during deal analysis."""
    # Setup - make the service throw an exception
    mock_market_service.get_historical_prices.side_effect = APIServiceUnavailableError("Market API unavailable")
    
    # Execute and verify
    with pytest.raises(DealAnalysisError):
        await deal_analysis_service.analyze_deal(mock_deal, mock_goal)
    
    # Verify method calls
    mock_market_service.get_historical_prices.assert_called_once()

@service_test
async def test_generate_simplified_analysis(
    deal_analysis_service,
    mock_deal
):
    """Test generating a simplified analysis."""
    # Setup
    with patch.object(deal_analysis_service, '_calculate_market_score', return_value=85), \
         patch.object(deal_analysis_service, '_calculate_price_score', return_value=75), \
         patch.object(deal_analysis_service, '_calculate_feature_match_score', return_value=90):
        
        # Execute
        result = await deal_analysis_service.generate_simplified_analysis(mock_deal)
        
        # Verify
        assert isinstance(result, AIAnalysis)
        assert result.deal_id == mock_deal.id
        assert 0 <= result.risk_score <= 100
        assert 0 <= result.confidence <= 1
        assert result.analysis_text is not None
        assert result.recommendation is not None
        assert isinstance(result.strengths, list)
        assert isinstance(result.weaknesses, list)

@service_test
async def test_analyze_price(
    deal_analysis_service,
    mock_deal,
    mock_price_history,
    mock_similar_deals
):
    """Test price analysis."""
    # Setup - expose the protected method for testing
    deal_analysis_service._analyze_price.__func__.__qualname__ = 'DealAnalysisService._analyze_price'
    
    # Execute
    result = await deal_analysis_service._analyze_price(mock_deal, mock_price_history, mock_similar_deals)
    
    # Verify
    assert isinstance(result, dict)
    assert "value_proposition" in result
    assert "price_trend" in result
    assert "relative_value" in result
    assert all(0 <= score <= 1 for score in result.values())

@service_test
async def test_analyze_historical_data(
    deal_analysis_service,
    mock_deal,
    mock_price_history
):
    """Test historical data analysis."""
    # Setup - expose the protected method for testing
    deal_analysis_service._analyze_historical_data.__func__.__qualname__ = 'DealAnalysisService._analyze_historical_data'
    
    # Execute
    result = await deal_analysis_service._analyze_historical_data(mock_deal, mock_price_history)
    
    # Verify
    assert isinstance(result, dict)
    assert "volatility" in result
    assert "consistent_growth" in result
    assert "price_stability" in result
    assert all(0 <= score <= 1 for score in result.values())

@service_test
async def test_analyze_market_data(
    deal_analysis_service,
    mock_deal,
    mock_similar_deals
):
    """Test market data analysis."""
    # Setup - expose the protected method for testing
    deal_analysis_service._analyze_market_data.__func__.__qualname__ = 'DealAnalysisService._analyze_market_data'
    
    # Execute
    result = await deal_analysis_service._analyze_market_data(mock_deal, mock_similar_deals)
    
    # Verify
    assert isinstance(result, dict)
    assert "market_strength" in result
    assert "competition" in result
    assert "market_readiness" in result
    assert all(0 <= score <= 1 for score in result.values())

@service_test
def test_analyze_goal_fit(
    deal_analysis_service,
    mock_deal,
    mock_goal
):
    """Test goal fit analysis."""
    # Execute
    result = deal_analysis_service._analyze_goal_fit(mock_deal, mock_goal)
    
    # Verify
    assert isinstance(result, dict)
    assert "feature_match" in result
    assert "target_metrics_match" in result
    assert "goal_alignment" in result
    assert all(0 <= score <= 1 for score in result.values())

@service_test
async def test_detect_anomalies(
    deal_analysis_service,
    mock_deal,
    mock_price_history,
    mock_similar_deals
):
    """Test anomaly detection."""
    # Setup - expose the protected method for testing
    deal_analysis_service._detect_anomalies.__func__.__qualname__ = 'DealAnalysisService._detect_anomalies'
    
    # Execute
    anomaly_score = await deal_analysis_service._detect_anomalies(
        mock_deal, 
        mock_price_history, 
        mock_similar_deals
    )
    
    # Verify
    assert 0 <= anomaly_score <= 1

@service_test
async def test_generate_recommendations(
    deal_analysis_service,
    mock_deal,
    mock_goal
):
    """Test recommendation generation."""
    # Setup - expose the protected method for testing
    deal_analysis_service._generate_recommendations.__func__.__qualname__ = 'DealAnalysisService._generate_recommendations'
    
    metrics = {
        'price': {'value_proposition': 0.8, 'price_trend': 0.7},
        'historical': {'volatility': 0.3, 'consistent_growth': 0.6},
        'market': {'market_strength': 0.8, 'competition': 0.4},
        'goal_fit': {'feature_match': 0.9, 'target_metrics_match': 0.7}
    }
    anomaly_score = 0.2
    
    # Execute
    recommendations = await deal_analysis_service._generate_recommendations(
        mock_deal, 
        metrics, 
        anomaly_score, 
        mock_goal
    )
    
    # Verify
    assert isinstance(recommendations, list)
    assert len(recommendations) > 0
    assert all(isinstance(rec, str) for rec in recommendations)

@service_test
def test_calculate_overall_score(deal_analysis_service):
    """Test overall score calculation."""
    # Setup
    metrics = {
        'price': {'value_proposition': 0.8, 'price_trend': 0.7},
        'historical': {'volatility': 0.3, 'consistent_growth': 0.6},
        'market': {'market_strength': 0.8, 'competition': 0.4},
        'goal_fit': {'feature_match': 0.9, 'target_metrics_match': 0.7}
    }
    confidence = 0.85
    
    # Execute
    score = deal_analysis_service._calculate_overall_score(metrics, confidence)
    
    # Verify
    assert 0 <= score <= 100 