"""Test WebSocket notifications functionality."""

# Standard library imports
import pytest
import json
from datetime import datetime
from uuid import UUID

# Third-party imports
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket

# Core imports
from core.models.goal import Goal
from core.models.deal import Deal
from core.models.enums import GoalStatus, NotificationType, NotificationPriority
from core.api.v1.notifications.websocket import NotificationManager, handle_websocket
from core.services.notifications import NotificationService
from core.websockets.price_updates import PriceUpdateManager

@pytest.mark.asyncio
class TestWebSocketNotifications:
    """Test cases for WebSocket notifications."""

    async def test_websocket_connection(
        self,
        async_client: AsyncClient,
        websocket_client: WebSocket,
        auth_headers: dict
    ):
        """Test WebSocket connection."""
        # Connect to WebSocket
        await websocket_client.connect(
            f"/ws/notifications?token={auth_headers['Authorization'].split()[1]}"
        )
        
        # Verify connection
        try:
            data = await websocket_client.receive_json()
            assert data["type"] == "connection_established"
        finally:
            await websocket_client.close()

    async def test_price_update_notifications(
        self,
        async_client: AsyncClient,
        websocket_client: WebSocket,
        auth_headers: dict,
        test_goal: Goal,
        test_deal: Deal,
        notification_manager: NotificationManager
    ):
        """Test price update notifications via WebSocket."""
        # Connect to WebSocket
        await websocket_client.connect(
            f"/ws/notifications?token={auth_headers['Authorization'].split()[1]}"
        )

        try:
            # Simulate price update
            price_update = {
                "deal_id": str(test_deal.id),
                "old_price": test_deal.price,
                "new_price": test_deal.price * 0.8,  # 20% price drop
                "timestamp": datetime.utcnow().isoformat()
            }

            # Send price update notification
            await notification_manager.send_price_update(
                user_id=test_goal.user_id,
                update_data=price_update
            )

            # Verify notification received
            data = await websocket_client.receive_json()
            assert data["type"] == "price_update"
            assert data["deal_id"] == str(test_deal.id)
            assert float(data["new_price"]) == test_deal.price * 0.8
        finally:
            await websocket_client.close()

    async def test_goal_status_notifications(
        self,
        async_client: AsyncClient,
        websocket_client: WebSocket,
        auth_headers: dict,
        test_goal: Goal,
        notification_manager: NotificationManager
    ):
        """Test goal status notifications via WebSocket."""
        # Connect to WebSocket
        await websocket_client.connect(
            f"/ws/notifications?token={auth_headers['Authorization'].split()[1]}"
        )

        try:
            # Update goal status
            test_goal.status = GoalStatus.COMPLETED
            status_update = {
                "goal_id": str(test_goal.id),
                "old_status": GoalStatus.ACTIVE,
                "new_status": GoalStatus.COMPLETED,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Send status update notification
            await notification_manager.send_goal_update(
                user_id=test_goal.user_id,
                update_data=status_update
            )

            # Verify notification received
            data = await websocket_client.receive_json()
            assert data["type"] == "goal_update"
            assert data["goal_id"] == str(test_goal.id)
            assert data["new_status"] == GoalStatus.COMPLETED.value
        finally:
            await websocket_client.close()

    async def test_deal_match_notifications(
        self,
        async_client: AsyncClient,
        websocket_client: WebSocket,
        auth_headers: dict,
        test_goal: Goal,
        notification_manager: NotificationManager
    ):
        """Test deal match notifications via WebSocket."""
        # Connect to WebSocket
        await websocket_client.connect(
            f"/ws/notifications?token={auth_headers['Authorization'].split()[1]}"
        )

        try:
            # Create a matching deal
            deal = Deal(
                goal_id=test_goal.id,
                title="Matching Deal",
                price=test_goal.constraints["max_price"] - 100,  # Good price
                url="https://example.com/deal",
                source="test"
            )

            # Send deal match notification
            await notification_manager.send_deal_match(
                user_id=test_goal.user_id,
                deal_data=deal.to_dict()
            )

            # Verify notification received
            data = await websocket_client.receive_json()
            assert data["type"] == "deal_match"
            assert data["goal_id"] == str(test_goal.id)
            assert float(data["price"]) == deal.price
        finally:
            await websocket_client.close()

    async def test_multiple_connections(
        self,
        async_client: AsyncClient,
        websocket_client: WebSocket,
        auth_headers: dict,
        notification_manager: NotificationManager
    ):
        """Test handling multiple WebSocket connections."""
        # Create multiple connections
        connections = []
        try:
            for i in range(3):
                ws = WebSocket()
                await ws.connect(
                    f"/ws/notifications?token={auth_headers['Authorization'].split()[1]}"
                )
                connections.append(ws)
                
                # Verify connection
                data = await ws.receive_json()
                assert data["type"] == "connection_established"

            # Send broadcast notification
            broadcast_msg = {
                "type": "system_update",
                "message": "Test broadcast message",
                "timestamp": datetime.utcnow().isoformat()
            }
            await notification_manager.broadcast(broadcast_msg)

            # Verify all connections received the message
            for ws in connections:
                data = await ws.receive_json()
                assert data["type"] == "system_update"
                assert data["message"] == "Test broadcast message"
        finally:
            for ws in connections:
                await ws.close()

    async def test_connection_error_handling(
        self,
        async_client: AsyncClient,
        websocket_client: WebSocket
    ):
        """Test WebSocket connection error handling."""
        # Test invalid token
        with pytest.raises(Exception):
            await websocket_client.connect("/ws/notifications?token=invalid")

        # Test missing token
        with pytest.raises(Exception):
            await websocket_client.connect("/ws/notifications")

    async def test_message_queuing(
        self,
        async_client: AsyncClient,
        websocket_client: WebSocket,
        auth_headers: dict,
        notification_manager: NotificationManager
    ):
        """Test message queuing when client is disconnected."""
        # Queue messages before connection
        messages = [
            {"type": "test", "id": i, "message": f"Test message {i}"}
            for i in range(5)
        ]
        for msg in messages:
            await notification_manager.queue_message(
                user_id=auth_headers["user_id"],
                message=msg
            )

        # Connect to WebSocket
        await websocket_client.connect(
            f"/ws/notifications?token={auth_headers['Authorization'].split()[1]}"
        )

        try:
            # Verify queued messages are received
            received_messages = []
            for _ in range(5):
                data = await websocket_client.receive_json()
                received_messages.append(data)

            # Verify all messages were received in order
            assert len(received_messages) == 5
            for i, msg in enumerate(received_messages):
                assert msg["id"] == messages[i]["id"]
                assert msg["message"] == messages[i]["message"]
        finally:
            await websocket_client.close()

    async def test_real_time_price_tracking(
        self,
        async_client: AsyncClient,
        websocket_client: WebSocket,
        auth_headers: dict,
        test_goal: Goal,
        test_deal: Deal,
        price_update_manager: PriceUpdateManager
    ):
        """Test real-time price tracking updates."""
        # Connect to WebSocket
        await websocket_client.connect(
            f"/ws/price-updates?token={auth_headers['Authorization'].split()[1]}"
        )

        try:
            # Subscribe to price updates
            await websocket_client.send_json({
                "action": "subscribe",
                "deal_ids": [str(test_deal.id)]
            })

            # Verify subscription confirmation
            data = await websocket_client.receive_json()
            assert data["type"] == "subscription_confirmed"
            assert str(test_deal.id) in data["subscribed_deals"]

            # Simulate price update
            await price_update_manager.update_price(
                deal_id=str(test_deal.id),
                new_price=test_deal.price * 0.9
            )

            # Verify update received
            data = await websocket_client.receive_json()
            assert data["type"] == "price_update"
            assert data["deal_id"] == str(test_deal.id)
            assert float(data["new_price"]) == test_deal.price * 0.9
        finally:
            await websocket_client.close() 