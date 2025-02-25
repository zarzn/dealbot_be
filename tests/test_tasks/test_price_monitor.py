"""Price monitoring task tests."""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
import aiohttp

from core.tasks.price_monitor import (
    monitor_price_changes,
    update_price_history,
    analyze_price_trends,
    trigger_price_alerts,
    PriceMonitorError,
    NetworkError,
    RateLimitError
)
from core.models.deal import Deal
from core.models.goal import Goal
from core.models.price_tracking import PricePoint
from core.models.notification import Notification

@pytest.mark.asyncio
async def test_monitor_price_changes(async_session: AsyncSession, test_deal):
    """Test monitoring price changes."""
    with patch('core.tasks.price_monitor.get_current_price') as mock_get_price:
        # Mock new price lower than current
        mock_get_price.return_value = Decimal("79.99")
        
        # Run price monitoring
        changes = await monitor_price_changes(async_session, [test_deal.id])
        
        assert len(changes) == 1
        assert changes[0]["deal_id"] == test_deal.id
        assert changes[0]["old_price"] == test_deal.price
        assert changes[0]["new_price"] == Decimal("79.99")
        assert changes[0]["price_drop"] == Decimal("20.00")  # 99.99 - 79.99

@pytest.mark.asyncio
async def test_update_price_history(async_session: AsyncSession, test_deal):
    """Test updating price history."""
    new_price = Decimal("79.99")
    
    # Update price history
    price_point = await update_price_history(
        async_session,
        deal_id=test_deal.id,
        new_price=new_price,
        source="amazon"
    )
    
    assert price_point.id is not None
    assert price_point.deal_id == test_deal.id
    assert price_point.price == new_price
    assert price_point.source == "amazon"
    assert isinstance(price_point.timestamp, datetime)

@pytest.mark.asyncio
async def test_analyze_price_trends(async_session: AsyncSession, test_deal):
    """Test analyzing price trends."""
    # Create price history
    prices = [
        Decimal("99.99"),  # Original price
        Decimal("89.99"),  # First drop
        Decimal("79.99"),  # Second drop
    ]
    
    for price in prices:
        price_point = PricePoint(
            deal_id=test_deal.id,
            price=price,
            source="amazon",
            timestamp=datetime.now(timezone.utc)
        )
        async_session.add(price_point)
    
    await async_session.commit()
    
    # Analyze trends
    trend = await analyze_price_trends(async_session, test_deal.id)
    
    assert trend["deal_id"] == test_deal.id
    assert trend["price_trend"] == "decreasing"
    assert trend["total_drop"] == Decimal("20.00")  # 99.99 - 79.99
    assert trend["drop_percentage"] == Decimal("20.00")  # 20% drop

@pytest.mark.asyncio
async def test_trigger_price_alerts(async_session: AsyncSession, test_deal, test_goal):
    """Test triggering price alerts."""
    # Set notification threshold on goal
    test_goal.notification_threshold = Decimal("0.15")  # 15% drop threshold
    await async_session.commit()
    
    price_change = {
        "deal_id": test_deal.id,
        "old_price": Decimal("99.99"),
        "new_price": Decimal("79.99"),
        "price_drop": Decimal("20.00"),
        "drop_percentage": Decimal("20.00")
    }
    
    with patch('core.tasks.price_monitor.create_notification') as mock_notify:
        # Trigger alerts
        await trigger_price_alerts(async_session, [price_change])
        
        # Verify notification was created
        mock_notify.assert_called_once()
        call_args = mock_notify.call_args[0]
        
        assert call_args[1] == test_goal.user_id  # user_id
        assert test_deal.id in str(call_args[2])  # message contains deal_id
        assert "20.00%" in str(call_args[2])  # message contains drop percentage

@pytest.mark.asyncio
async def test_no_alert_below_threshold(async_session: AsyncSession, test_deal, test_goal):
    """Test no alert is triggered when price drop is below threshold."""
    # Set notification threshold on goal
    test_goal.notification_threshold = Decimal("0.25")  # 25% drop threshold
    await async_session.commit()
    
    price_change = {
        "deal_id": test_deal.id,
        "old_price": Decimal("99.99"),
        "new_price": Decimal("89.99"),
        "price_drop": Decimal("10.00"),
        "drop_percentage": Decimal("10.00")
    }
    
    with patch('core.tasks.price_monitor.create_notification') as mock_notify:
        # Trigger alerts
        await trigger_price_alerts(async_session, [price_change])
        
        # Verify no notification was created
        mock_notify.assert_not_called()

@pytest.mark.asyncio
async def test_auto_buy_trigger(async_session: AsyncSession, test_deal, test_goal):
    """Test auto-buy trigger when price drop exceeds threshold."""
    # Set auto-buy threshold on goal
    test_goal.auto_buy_threshold = Decimal("0.30")  # 30% drop threshold
    await async_session.commit()
    
    price_change = {
        "deal_id": test_deal.id,
        "old_price": Decimal("99.99"),
        "new_price": Decimal("69.99"),
        "price_drop": Decimal("30.00"),
        "drop_percentage": Decimal("30.00")
    }
    
    with patch('core.tasks.price_monitor.trigger_auto_buy') as mock_auto_buy:
        # Trigger alerts
        await trigger_price_alerts(async_session, [price_change])
        
        # Verify auto-buy was triggered
        mock_auto_buy.assert_called_once_with(
            async_session,
            test_deal.id,
            test_goal.id
        )

@pytest.mark.asyncio
async def test_price_history_retention(async_session: AsyncSession, test_deal):
    """Test price history retention policy."""
    # Create old price points
    old_date = datetime.now(timezone.utc) - timedelta(days=90)
    
    for i in range(5):
        price_point = PricePoint(
            deal_id=test_deal.id,
            price=Decimal("99.99") - i * 5,
            source="amazon",
            timestamp=old_date + timedelta(days=i)
        )
        async_session.add(price_point)
    
    await async_session.commit()
    
    # Add new price point
    new_price = Decimal("79.99")
    await update_price_history(
        async_session,
        deal_id=test_deal.id,
        new_price=new_price,
        source="amazon"
    )
    
    # Verify old price points are cleaned up
    price_points = await async_session.query(PricePoint).filter(
        PricePoint.deal_id == test_deal.id
    ).all()
    
    # Should only keep last 30 days of price points
    timestamps = [pp.timestamp for pp in price_points]
    oldest_allowed = datetime.now(timezone.utc) - timedelta(days=30)
    
    for ts in timestamps:
        assert ts >= oldest_allowed 

@pytest.mark.asyncio
async def test_price_increase(async_session: AsyncSession, test_deal):
    """Test handling of price increases."""
    with patch('core.tasks.price_monitor.get_current_price') as mock_get_price:
        # Mock new price higher than current
        mock_get_price.return_value = Decimal("119.99")
        
        # Run price monitoring
        changes = await monitor_price_changes(async_session, [test_deal.id])
        
        assert len(changes) == 1
        assert changes[0]["deal_id"] == test_deal.id
        assert changes[0]["old_price"] == test_deal.price
        assert changes[0]["new_price"] == Decimal("119.99")
        assert changes[0]["price_change"] == Decimal("20.00")  # 119.99 - 99.99
        assert changes[0]["is_increase"] is True

@pytest.mark.asyncio
async def test_multiple_deals_monitoring(async_session: AsyncSession, test_deal):
    """Test monitoring multiple deals simultaneously."""
    # Create additional test deal
    deal2 = Deal(
        user_id=test_deal.user_id,
        goal_id=test_deal.goal_id,
        market_id=test_deal.market_id,
        title="Test Deal 2",
        description="Another test deal",
        url="https://example.com/test-deal-2",
        price=Decimal("199.99"),
        original_price=Decimal("249.99"),
        currency="USD",
        source="amazon",
        category="electronics",
        status="active"
    )
    async_session.add(deal2)
    await async_session.commit()

    with patch('core.tasks.price_monitor.get_current_price') as mock_get_price:
        # Mock different prices for different deals
        mock_get_price.side_effect = [
            Decimal("79.99"),   # First deal price drop
            Decimal("179.99")   # Second deal price drop
        ]
        
        # Monitor both deals
        changes = await monitor_price_changes(
            async_session,
            [test_deal.id, deal2.id]
        )
        
        assert len(changes) == 2
        assert changes[0]["deal_id"] == test_deal.id
        assert changes[0]["price_drop"] == Decimal("20.00")
        assert changes[1]["deal_id"] == deal2.id
        assert changes[1]["price_drop"] == Decimal("20.00")

@pytest.mark.asyncio
async def test_invalid_deal_handling(async_session: AsyncSession):
    """Test handling of invalid deal IDs."""
    import uuid
    invalid_id = uuid.uuid4()
    
    with pytest.raises(PriceMonitorError, match="Deal not found"):
        await monitor_price_changes(async_session, [invalid_id])

@pytest.mark.asyncio
async def test_market_specific_price_updates(async_session: AsyncSession, test_deal):
    """Test market-specific price update handling."""
    # Create price points from different sources
    sources = ["amazon", "walmart", "ebay"]
    prices = [Decimal("99.99"), Decimal("89.99"), Decimal("94.99")]
    
    for source, price in zip(sources, prices):
        price_point = PricePoint(
            deal_id=test_deal.id,
            price=price,
            source=source,
            timestamp=datetime.now(timezone.utc)
        )
        async_session.add(price_point)
    
    await async_session.commit()
    
    # Update price for specific market
    new_price = Decimal("79.99")
    price_point = await update_price_history(
        async_session,
        deal_id=test_deal.id,
        new_price=new_price,
        source="amazon"
    )
    
    # Verify market-specific update
    price_points = await async_session.query(PricePoint).filter(
        PricePoint.deal_id == test_deal.id,
        PricePoint.source == "amazon"
    ).order_by(PricePoint.timestamp.desc()).all()
    
    assert len(price_points) > 0
    assert price_points[0].price == new_price
    assert price_points[0].source == "amazon"

@pytest.mark.asyncio
async def test_price_trend_with_fluctuations(async_session: AsyncSession, test_deal):
    """Test price trend analysis with price fluctuations."""
    # Create price history with fluctuations
    prices = [
        Decimal("99.99"),   # Original price
        Decimal("89.99"),   # Drop
        Decimal("94.99"),   # Increase
        Decimal("92.99"),   # Drop
        Decimal("96.99"),   # Increase
    ]
    
    for price in prices:
        price_point = PricePoint(
            deal_id=test_deal.id,
            price=price,
            source="amazon",
            timestamp=datetime.now(timezone.utc)
        )
        async_session.add(price_point)
    
    await async_session.commit()
    
    # Analyze trends
    trend = await analyze_price_trends(async_session, test_deal.id)
    
    assert trend["deal_id"] == test_deal.id
    assert trend["price_trend"] == "fluctuating"
    assert trend["volatility"] > 0
    assert "min_price" in trend
    assert "max_price" in trend
    assert "avg_price" in trend

@pytest.mark.asyncio
async def test_concurrent_price_updates(async_session: AsyncSession, test_deal):
    """Test handling of concurrent price updates."""
    async def update_1():
        async with async_session_maker() as session1:
            await update_price_history(
                session1,
                deal_id=test_deal.id,
                new_price=Decimal("89.99"),
                source="amazon"
            )

    async def update_2():
        async with async_session_maker() as session2:
            await update_price_history(
                session2,
                deal_id=test_deal.id,
                new_price=Decimal("79.99"),
                source="amazon"
            )

    # Run updates concurrently
    await asyncio.gather(update_1(), update_2())

    # Verify both updates were recorded in correct order
    price_points = await async_session.query(PricePoint).filter(
        PricePoint.deal_id == test_deal.id,
        PricePoint.source == "amazon"
    ).order_by(PricePoint.timestamp.desc()).all()

    assert len(price_points) >= 2
    assert price_points[0].price == Decimal("79.99")
    assert price_points[1].price == Decimal("89.99") 

@pytest.mark.asyncio
async def test_network_error_handling(async_session: AsyncSession, test_deal):
    """Test handling of network errors during price monitoring."""
    with patch('core.tasks.price_monitor.get_current_price') as mock_get_price:
        mock_get_price.side_effect = aiohttp.ClientError("Network error")
        
        with pytest.raises(NetworkError, match="Failed to fetch price"):
            await monitor_price_changes(async_session, [test_deal.id])

@pytest.mark.asyncio
async def test_rate_limit_handling(async_session: AsyncSession, test_deal):
    """Test handling of rate limits."""
    with patch('core.tasks.price_monitor.get_current_price') as mock_get_price:
        mock_get_price.side_effect = RateLimitError("Rate limit exceeded")
        
        # Should handle rate limit and retry
        with patch('asyncio.sleep') as mock_sleep:
            changes = await monitor_price_changes(
                async_session,
                [test_deal.id],
                retry_count=3
            )
            
            assert mock_sleep.called
            assert mock_sleep.call_count == 3

@pytest.mark.asyncio
async def test_price_update_validation(async_session: AsyncSession, test_deal):
    """Test validation of price updates."""
    with pytest.raises(PriceMonitorError, match="Invalid price value"):
        await update_price_history(
            async_session,
            deal_id=test_deal.id,
            new_price=Decimal("-1.0"),  # Invalid negative price
            source="amazon"
        )

@pytest.mark.asyncio
async def test_notification_throttling(async_session: AsyncSession, test_deal, test_goal):
    """Test notification throttling for frequent price changes."""
    # Set notification threshold
    test_goal.notification_threshold = Decimal("0.15")  # 15% drop threshold
    await async_session.commit()
    
    # Create recent notification
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    notification = Notification(
        user_id=test_goal.user_id,
        goal_id=test_goal.id,
        deal_id=test_deal.id,
        title="Price Drop Alert",
        message="Price dropped by 20%",
        type="price_alert",
        created_at=recent_time
    )
    async_session.add(notification)
    await async_session.commit()
    
    # Try to create another notification too soon
    price_change = {
        "deal_id": test_deal.id,
        "old_price": Decimal("99.99"),
        "new_price": Decimal("79.99"),
        "price_drop": Decimal("20.00"),
        "drop_percentage": Decimal("20.00")
    }
    
    with patch('core.tasks.price_monitor.create_notification') as mock_notify:
        await trigger_price_alerts(async_session, [price_change])
        
        # Should not create new notification due to throttling
        mock_notify.assert_not_called()

@pytest.mark.asyncio
async def test_market_specific_rate_limits(async_session: AsyncSession, test_deal):
    """Test market-specific rate limit handling."""
    # Create deals from different markets
    deals = []
    for source in ["amazon", "walmart", "ebay"]:
        deal = Deal(
            user_id=test_deal.user_id,
            goal_id=test_deal.goal_id,
            market_id=test_deal.market_id,
            title=f"Test Deal - {source}",
            description="Test deal description",
            url=f"https://example.com/test-deal-{source}",
            price=Decimal("99.99"),
            original_price=Decimal("149.99"),
            currency="USD",
            source=source,
            category="electronics",
            status="active"
        )
        async_session.add(deal)
        deals.append(deal)
    
    await async_session.commit()
    
    with patch('core.tasks.price_monitor.get_current_price') as mock_get_price:
        # Simulate rate limit for specific market
        def side_effect(deal):
            if deal.source == "amazon":
                raise RateLimitError("Rate limit exceeded for Amazon")
            return Decimal("89.99")
        
        mock_get_price.side_effect = side_effect
        
        # Should continue monitoring other markets when one fails
        changes = await monitor_price_changes(
            async_session,
            [d.id for d in deals]
        )
        
        assert len(changes) == 2  # Should have results for walmart and ebay
        assert all(c["new_price"] == Decimal("89.99") for c in changes)

@pytest.mark.asyncio
async def test_price_trend_analysis_with_gaps(async_session: AsyncSession, test_deal):
    """Test price trend analysis with missing data points."""
    # Create price history with gaps
    timestamps = [
        datetime.now(timezone.utc) - timedelta(days=d)
        for d in [30, 25, 15, 10, 5, 0]  # Gaps between points
    ]
    
    prices = [
        Decimal("99.99"),
        Decimal("89.99"),
        Decimal("94.99"),
        Decimal("92.99"),
        Decimal("88.99"),
        Decimal("85.99")
    ]
    
    for ts, price in zip(timestamps, prices):
        price_point = PricePoint(
            deal_id=test_deal.id,
            price=price,
            source="amazon",
            timestamp=ts
        )
        async_session.add(price_point)
    
    await async_session.commit()
    
    # Analyze trends with gaps
    trend = await analyze_price_trends(async_session, test_deal.id)
    
    assert trend["deal_id"] == test_deal.id
    assert trend["price_trend"] == "decreasing"  # Overall trend
    assert trend["confidence"] < 1.0  # Lower confidence due to gaps
    assert trend["data_quality"] == "sparse" 