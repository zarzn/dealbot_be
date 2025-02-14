"""Integration tests for price tracking and prediction components."""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from fastapi import WebSocket
from httpx import AsyncClient

from core.services.price_tracking import PriceTrackingService
from core.services.price_prediction import PricePredictionService
from core.websockets.price_updates import PriceUpdateManager
from core.models.price_tracking import PriceTrackerCreate, PricePointCreate
from core.models.price_prediction import PricePredictionCreate
from core.models.deal import Deal

@pytest.fixture
async def test_deal(async_session):
    """Create a test deal."""
    deal = Deal(
        id=UUID('12345678-1234-5678-1234-567812345678'),
        title="Test Deal",
        price=Decimal('100.00'),
        currency="USD",
        url="https://test.com/deal",
        source="test_source"
    )
    async_session.add(deal)
    await async_session.commit()
    return deal

@pytest.fixture
async def price_tracking_service(async_session):
    """Create price tracking service instance."""
    return PriceTrackingService(async_session)

@pytest.fixture
async def price_prediction_service(async_session):
    """Create price prediction service instance."""
    return PricePredictionService(async_session)

@pytest.fixture
async def price_update_manager():
    """Create price update manager instance."""
    manager = PriceUpdateManager()
    yield manager
    await manager.stop_background_tasks()

@pytest.mark.asyncio
async def test_price_tracking_creation(
    async_session,
    price_tracking_service,
    test_deal
):
    """Test creating a price tracker."""
    tracker_data = PriceTrackerCreate(
        deal_id=test_deal.id,
        threshold_price=Decimal('90.00'),
        check_interval=300
    )
    
    tracker = await price_tracking_service.create_tracker(
        tracker_data=tracker_data,
        user_id=UUID('00000000-0000-0000-0000-000000000001')
    )
    
    assert tracker is not None
    assert tracker.deal_id == test_deal.id
    assert tracker.threshold_price == Decimal('90.00')
    assert tracker.is_active is True

@pytest.mark.asyncio
async def test_price_point_addition(
    async_session,
    price_tracking_service,
    test_deal,
    price_update_manager
):
    """Test adding price points and real-time updates."""
    # Create tracker
    tracker_data = PriceTrackerCreate(
        deal_id=test_deal.id,
        threshold_price=Decimal('90.00')
    )
    tracker = await price_tracking_service.create_tracker(
        tracker_data=tracker_data,
        user_id=UUID('00000000-0000-0000-0000-000000000001')
    )
    
    # Add price point
    price_point = PricePointCreate(
        deal_id=test_deal.id,
        price=Decimal('95.00'),
        currency="USD",
        source="test"
    )
    
    point_response = await price_tracking_service.add_price_point(
        tracker_id=tracker.id,
        user_id=UUID('00000000-0000-0000-0000-000000000001'),
        price_point=price_point
    )
    
    assert point_response is not None
    assert point_response.price == Decimal('95.00')

@pytest.mark.asyncio
async def test_price_prediction_integration(
    async_session,
    price_tracking_service,
    price_prediction_service,
    test_deal
):
    """Test price prediction with tracking data."""
    # Create tracker and add multiple price points
    tracker_data = PriceTrackerCreate(
        deal_id=test_deal.id,
        threshold_price=Decimal('90.00')
    )
    tracker = await price_tracking_service.create_tracker(
        tracker_data=tracker_data,
        user_id=UUID('00000000-0000-0000-0000-000000000001')
    )
    
    # Add historical price points
    base_price = Decimal('100.00')
    for i in range(35):  # Add 35 points for minimum history
        price_point = PricePointCreate(
            deal_id=test_deal.id,
            price=base_price + Decimal(str(i % 10)),  # Create some pattern
            currency="USD",
            source="test"
        )
        await price_tracking_service.add_price_point(
            tracker_id=tracker.id,
            user_id=UUID('00000000-0000-0000-0000-000000000001'),
            price_point=price_point
        )
    
    # Create prediction
    prediction_data = PricePredictionCreate(
        deal_id=test_deal.id,
        prediction_days=7,
        confidence_threshold=0.8
    )
    
    prediction = await price_prediction_service.create_prediction(
        prediction_data=prediction_data,
        user_id=UUID('00000000-0000-0000-0000-000000000001')
    )
    
    assert prediction is not None
    assert prediction.deal_id == test_deal.id
    assert len(prediction.predictions) > 0

@pytest.mark.asyncio
async def test_websocket_integration(
    async_session,
    price_tracking_service,
    price_update_manager,
    test_deal,
    test_client: AsyncClient
):
    """Test WebSocket updates for price changes."""
    # Create tracker
    tracker_data = PriceTrackerCreate(
        deal_id=test_deal.id,
        threshold_price=Decimal('90.00')
    )
    tracker = await price_tracking_service.create_tracker(
        tracker_data=tracker_data,
        user_id=UUID('00000000-0000-0000-0000-000000000001')
    )
    
    # Setup WebSocket connection
    async with test_client.websocket_connect(
        f"/api/v1/price-tracking/ws/00000000-0000-0000-0000-000000000001"
    ) as websocket:
        # Subscribe to deal updates
        await websocket.send_json({
            "action": "subscribe",
            "deal_id": str(test_deal.id)
        })
        
        # Add price point
        price_point = PricePointCreate(
            deal_id=test_deal.id,
            price=Decimal('85.00'),
            currency="USD",
            source="test"
        )
        
        await price_tracking_service.add_price_point(
            tracker_id=tracker.id,
            user_id=UUID('00000000-0000-0000-0000-000000000001'),
            price_point=price_point
        )
        
        # Wait for WebSocket update
        data = await websocket.receive_json()
        assert data["deal_id"] == str(test_deal.id)
        assert Decimal(data["price"]) == Decimal('85.00')

@pytest.mark.asyncio
async def test_threshold_notifications(
    async_session,
    price_tracking_service,
    test_deal
):
    """Test threshold notifications when price changes."""
    # Create tracker with threshold
    tracker_data = PriceTrackerCreate(
        deal_id=test_deal.id,
        threshold_price=Decimal('95.00')
    )
    tracker = await price_tracking_service.create_tracker(
        tracker_data=tracker_data,
        user_id=UUID('00000000-0000-0000-0000-000000000001')
    )
    
    # Add price point below threshold
    price_point = PricePointCreate(
        deal_id=test_deal.id,
        price=Decimal('93.00'),
        currency="USD",
        source="test"
    )
    
    point_response = await price_tracking_service.add_price_point(
        tracker_id=tracker.id,
        user_id=UUID('00000000-0000-0000-0000-000000000001'),
        price_point=price_point
    )
    
    # Verify notification was triggered (check notification service mock)
    notifications = await async_session.execute(
        "SELECT * FROM notifications WHERE deal_id = :deal_id",
        {"deal_id": test_deal.id}
    )
    assert len(notifications) > 0

@pytest.mark.asyncio
async def test_full_integration_flow(
    async_session,
    price_tracking_service,
    price_prediction_service,
    price_update_manager,
    test_deal,
    test_client: AsyncClient
):
    """Test complete integration flow with all components."""
    user_id = UUID('00000000-0000-0000-0000-000000000001')
    
    # 1. Create price tracker
    tracker_data = PriceTrackerCreate(
        deal_id=test_deal.id,
        threshold_price=Decimal('90.00')
    )
    tracker = await price_tracking_service.create_tracker(
        tracker_data=tracker_data,
        user_id=user_id
    )
    
    # 2. Connect to WebSocket
    async with test_client.websocket_connect(
        f"/api/v1/price-tracking/ws/{user_id}"
    ) as websocket:
        await websocket.send_json({
            "action": "subscribe",
            "deal_id": str(test_deal.id)
        })
        
        # 3. Add price points
        base_price = Decimal('100.00')
        for i in range(35):
            price_point = PricePointCreate(
                deal_id=test_deal.id,
                price=base_price - Decimal(str(i * 0.5)),
                currency="USD",
                source="test"
            )
            await price_tracking_service.add_price_point(
                tracker_id=tracker.id,
                user_id=user_id,
                price_point=price_point
            )
            
            # Verify WebSocket update
            data = await websocket.receive_json()
            assert data["deal_id"] == str(test_deal.id)
        
        # 4. Generate prediction
        prediction_data = PricePredictionCreate(
            deal_id=test_deal.id,
            prediction_days=7,
            confidence_threshold=0.8
        )
        
        prediction = await price_prediction_service.create_prediction(
            prediction_data=prediction_data,
            user_id=user_id
        )
        
        assert prediction is not None
        assert len(prediction.predictions) > 0
        
        # 5. Verify threshold notification
        price_point = PricePointCreate(
            deal_id=test_deal.id,
            price=Decimal('85.00'),  # Below threshold
            currency="USD",
            source="test"
        )
        
        await price_tracking_service.add_price_point(
            tracker_id=tracker.id,
            user_id=user_id,
            price_point=price_point
        )
        
        # Verify notification
        notifications = await async_session.execute(
            "SELECT * FROM notifications WHERE deal_id = :deal_id",
            {"deal_id": test_deal.id}
        )
        assert len(notifications) > 0
        
        # Verify WebSocket update
        data = await websocket.receive_json()
        assert data["deal_id"] == str(test_deal.id)
        assert Decimal(data["price"]) == Decimal('85.00') 