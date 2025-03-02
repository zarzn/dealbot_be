"""Tests for the deal updates WebSocket functionality."""

import pytest
import asyncio
import json
import uuid
from typing import Dict, Any, List, AsyncGenerator
from fastapi import WebSocket, WebSocketDisconnect
from httpx import AsyncClient

from core.models.enums import DealStatus, MarketType
from core.api.dependencies import get_current_user
from core.models.user import User
from core.models.deal import Deal
from core.api.websockets.connection_manager import get_connection_manager

class MockWebSocket:
    """Mock WebSocket client for testing."""
    
    def __init__(self):
        self.received_messages = []
        self.client_id = str(uuid.uuid4())
        self.connected = True
        self.closed = False
        self.close_code = None
    
    async def receive_json(self) -> Dict[str, Any]:
        """Simulate receiving a message from the WebSocket."""
        if not self.connected:
            raise WebSocketDisconnect(code=1000)
        
        # Wait for a message to be added to the queue
        while not self.received_messages and self.connected:
            await asyncio.sleep(0.01)
        
        if not self.connected:
            raise WebSocketDisconnect(code=self.close_code or 1000)
        
        return self.received_messages.pop(0) if self.received_messages else None
    
    async def send_json(self, data: Dict[str, Any]) -> None:
        """Simulate sending a message to the WebSocket."""
        if not self.connected:
            raise WebSocketDisconnect(code=1000)
        self.received_messages.append(data)
    
    async def close(self, code: int = 1000) -> None:
        """Simulate closing the WebSocket connection."""
        self.connected = False
        self.closed = True
        self.close_code = code

@pytest.fixture
def auth_override():
    """Override authentication for tests."""
    async def mock_get_current_user():
        return User(
            id=uuid.uuid4(),
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            is_active=True,
            is_superuser=False
        )
    
    return mock_get_current_user

@pytest.fixture
async def authenticated_client(app, auth_override):
    """Create an authenticated test client."""
    app.dependency_overrides[get_current_user] = auth_override
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides = {}

@pytest.fixture
async def sample_deal(db_session):
    """Create a sample deal for testing."""
    deal = Deal(
        title="Test Deal",
        description="This is a test deal for WebSocket testing",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=uuid.uuid4(),
        metadata={"test_key": "test_value"}
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    return deal

@pytest.fixture
async def mock_websocket():
    """Create a mock WebSocket for testing."""
    return MockWebSocket()

@pytest.fixture
async def connection_manager():
    """Get the WebSocket connection manager."""
    return get_connection_manager()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_websocket_connection(connection_manager, mock_websocket, auth_override):
    """Test establishing a WebSocket connection."""
    # Connect the mock WebSocket
    user = await auth_override()
    await connection_manager.connect(mock_websocket, user.id)
    
    # Verify the connection was established
    assert mock_websocket.client_id in connection_manager.active_connections
    assert connection_manager.active_connections[mock_websocket.client_id]["user_id"] == user.id
    
    # Clean up
    await connection_manager.disconnect(mock_websocket)
    assert mock_websocket.client_id not in connection_manager.active_connections

@pytest.mark.asyncio
@pytest.mark.integration
async def test_deal_update_notification(connection_manager, mock_websocket, authenticated_client, 
                                        sample_deal, auth_override):
    """Test receiving deal update notifications via WebSocket."""
    # Connect the mock WebSocket
    user = await auth_override()
    await connection_manager.connect(mock_websocket, user.id)
    
    # Subscribe to deal updates
    await connection_manager.subscribe_to_deal(mock_websocket, str(sample_deal.id))
    
    # Update the deal via API
    update_data = {
        "title": "Updated Deal Title",
        "status": DealStatus.ACTIVE.value
    }
    
    # Create a task to listen for WebSocket messages
    async def listen_for_messages():
        try:
            message = await asyncio.wait_for(mock_websocket.receive_json(), timeout=2.0)
            return message
        except asyncio.TimeoutError:
            return None
    
    # Start listening for messages
    listen_task = asyncio.create_task(listen_for_messages())
    
    # Update the deal
    response = await authenticated_client.patch(
        f"/api/v1/deals/{sample_deal.id}",
        json=update_data
    )
    assert response.status_code == 200
    
    # Wait for the WebSocket message
    message = await listen_task
    
    # Verify we received a notification about the deal update
    assert message is not None
    assert message["type"] == "deal_update"
    assert message["data"]["id"] == str(sample_deal.id)
    assert message["data"]["title"] == update_data["title"]
    assert message["data"]["status"] == update_data["status"].lower()
    
    # Clean up
    await connection_manager.disconnect(mock_websocket)

@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_clients_notification(connection_manager, authenticated_client, 
                                             sample_deal, auth_override):
    """Test notifications to multiple WebSocket clients."""
    # Create multiple mock WebSockets
    mock_websocket1 = MockWebSocket()
    mock_websocket2 = MockWebSocket()
    mock_websocket3 = MockWebSocket()
    
    # Connect all WebSockets
    user = await auth_override()
    await connection_manager.connect(mock_websocket1, user.id)
    await connection_manager.connect(mock_websocket2, user.id)
    await connection_manager.connect(mock_websocket3, user.id)
    
    # Subscribe WebSockets 1 and 2 to the deal, but not 3
    await connection_manager.subscribe_to_deal(mock_websocket1, str(sample_deal.id))
    await connection_manager.subscribe_to_deal(mock_websocket2, str(sample_deal.id))
    
    # Update the deal
    update_data = {
        "title": "Multi-Client Test",
        "status": DealStatus.ACTIVE.value
    }
    
    # Create tasks to listen for WebSocket messages
    async def listen_for_messages(websocket):
        try:
            message = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
            return message
        except asyncio.TimeoutError:
            return None
    
    # Start listening for messages on all WebSockets
    listen_task1 = asyncio.create_task(listen_for_messages(mock_websocket1))
    listen_task2 = asyncio.create_task(listen_for_messages(mock_websocket2))
    listen_task3 = asyncio.create_task(listen_for_messages(mock_websocket3))
    
    # Update the deal
    response = await authenticated_client.patch(
        f"/api/v1/deals/{sample_deal.id}",
        json=update_data
    )
    assert response.status_code == 200
    
    # Wait for the WebSocket messages
    message1 = await listen_task1
    message2 = await listen_task2
    message3 = await listen_task3
    
    # Verify WebSockets 1 and 2 received notifications
    assert message1 is not None
    assert message1["type"] == "deal_update"
    assert message1["data"]["id"] == str(sample_deal.id)
    
    assert message2 is not None
    assert message2["type"] == "deal_update"
    assert message2["data"]["id"] == str(sample_deal.id)
    
    # Verify WebSocket 3 did not receive a notification
    assert message3 is None
    
    # Clean up
    await connection_manager.disconnect(mock_websocket1)
    await connection_manager.disconnect(mock_websocket2)
    await connection_manager.disconnect(mock_websocket3)

@pytest.mark.asyncio
@pytest.mark.integration
async def test_unsubscribe_from_deal(connection_manager, mock_websocket, authenticated_client, 
                                     sample_deal, auth_override):
    """Test unsubscribing from deal updates."""
    # Connect the mock WebSocket
    user = await auth_override()
    await connection_manager.connect(mock_websocket, user.id)
    
    # Subscribe to deal updates
    await connection_manager.subscribe_to_deal(mock_websocket, str(sample_deal.id))
    
    # Unsubscribe from deal updates
    await connection_manager.unsubscribe_from_deal(mock_websocket, str(sample_deal.id))
    
    # Update the deal
    update_data = {
        "title": "Unsubscribe Test",
        "status": DealStatus.ACTIVE.value
    }
    
    # Create a task to listen for WebSocket messages
    async def listen_for_messages():
        try:
            message = await asyncio.wait_for(mock_websocket.receive_json(), timeout=1.0)
            return message
        except asyncio.TimeoutError:
            return None
    
    # Start listening for messages
    listen_task = asyncio.create_task(listen_for_messages())
    
    # Update the deal
    response = await authenticated_client.patch(
        f"/api/v1/deals/{sample_deal.id}",
        json=update_data
    )
    assert response.status_code == 200
    
    # Wait for the WebSocket message
    message = await listen_task
    
    # Verify we did not receive a notification after unsubscribing
    assert message is None
    
    # Clean up
    await connection_manager.disconnect(mock_websocket)

@pytest.mark.asyncio
@pytest.mark.integration
async def test_websocket_authentication(app, connection_manager):
    """Test WebSocket authentication requirements."""
    # Create a mock WebSocket
    mock_websocket = MockWebSocket()
    
    # Try to connect without authentication
    # This should be handled by the WebSocket endpoint's dependency
    # For testing purposes, we'll simulate the authentication failure
    
    # In a real application, the WebSocket endpoint would handle authentication
    # and reject the connection if authentication fails
    
    # For this test, we'll verify that the connection manager properly
    # handles user_id being required for connections
    
    # Try to connect without a user_id (should raise an exception)
    with pytest.raises(ValueError, match="User ID is required"):
        await connection_manager.connect(mock_websocket, None)
    
    # Verify the connection was not established
    assert mock_websocket.client_id not in connection_manager.active_connections

@pytest.mark.asyncio
@pytest.mark.integration
async def test_websocket_disconnect_handling(connection_manager, mock_websocket, auth_override):
    """Test handling WebSocket disconnections."""
    # Connect the mock WebSocket
    user = await auth_override()
    await connection_manager.connect(mock_websocket, user.id)
    
    # Subscribe to a deal
    deal_id = str(uuid.uuid4())
    await connection_manager.subscribe_to_deal(mock_websocket, deal_id)
    
    # Verify the subscription
    assert deal_id in connection_manager.deal_subscriptions
    assert mock_websocket.client_id in connection_manager.deal_subscriptions[deal_id]
    
    # Simulate a client disconnect
    await connection_manager.disconnect(mock_websocket)
    
    # Verify the connection and subscriptions were cleaned up
    assert mock_websocket.client_id not in connection_manager.active_connections
    assert deal_id in connection_manager.deal_subscriptions
    assert mock_websocket.client_id not in connection_manager.deal_subscriptions[deal_id]

@pytest.mark.asyncio
@pytest.mark.integration
async def test_broadcast_to_all_clients(connection_manager, auth_override):
    """Test broadcasting messages to all connected clients."""
    # Create multiple mock WebSockets
    mock_websocket1 = MockWebSocket()
    mock_websocket2 = MockWebSocket()
    mock_websocket3 = MockWebSocket()
    
    # Connect all WebSockets
    user = await auth_override()
    await connection_manager.connect(mock_websocket1, user.id)
    await connection_manager.connect(mock_websocket2, user.id)
    await connection_manager.connect(mock_websocket3, user.id)
    
    # Broadcast a message to all clients
    broadcast_message = {
        "type": "system_notification",
        "data": {
            "message": "System maintenance in 10 minutes",
            "severity": "info"
        }
    }
    
    await connection_manager.broadcast(broadcast_message)
    
    # Verify all clients received the message
    assert len(mock_websocket1.received_messages) == 1
    assert mock_websocket1.received_messages[0] == broadcast_message
    
    assert len(mock_websocket2.received_messages) == 1
    assert mock_websocket2.received_messages[0] == broadcast_message
    
    assert len(mock_websocket3.received_messages) == 1
    assert mock_websocket3.received_messages[0] == broadcast_message
    
    # Clean up
    await connection_manager.disconnect(mock_websocket1)
    await connection_manager.disconnect(mock_websocket2)
    await connection_manager.disconnect(mock_websocket3) 

import pytest
import asyncio
import json
import uuid
from typing import Dict, Any, List, AsyncGenerator
from fastapi import WebSocket, WebSocketDisconnect
from httpx import AsyncClient

from core.models.enums import DealStatus, MarketType
from core.api.dependencies import get_current_user
from core.models.user import User
from core.models.deal import Deal
from core.api.websockets.connection_manager import get_connection_manager

class MockWebSocket:
    """Mock WebSocket client for testing."""
    
    def __init__(self):
        self.received_messages = []
        self.client_id = str(uuid.uuid4())
        self.connected = True
        self.closed = False
        self.close_code = None
    
    async def receive_json(self) -> Dict[str, Any]:
        """Simulate receiving a message from the WebSocket."""
        if not self.connected:
            raise WebSocketDisconnect(code=1000)
        
        # Wait for a message to be added to the queue
        while not self.received_messages and self.connected:
            await asyncio.sleep(0.01)
        
        if not self.connected:
            raise WebSocketDisconnect(code=self.close_code or 1000)
        
        return self.received_messages.pop(0) if self.received_messages else None
    
    async def send_json(self, data: Dict[str, Any]) -> None:
        """Simulate sending a message to the WebSocket."""
        if not self.connected:
            raise WebSocketDisconnect(code=1000)
        self.received_messages.append(data)
    
    async def close(self, code: int = 1000) -> None:
        """Simulate closing the WebSocket connection."""
        self.connected = False
        self.closed = True
        self.close_code = code

@pytest.fixture
def auth_override():
    """Override authentication for tests."""
    async def mock_get_current_user():
        return User(
            id=uuid.uuid4(),
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            is_active=True,
            is_superuser=False
        )
    
    return mock_get_current_user

@pytest.fixture
async def authenticated_client(app, auth_override):
    """Create an authenticated test client."""
    app.dependency_overrides[get_current_user] = auth_override
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides = {}

@pytest.fixture
async def sample_deal(db_session):
    """Create a sample deal for testing."""
    deal = Deal(
        title="Test Deal",
        description="This is a test deal for WebSocket testing",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=uuid.uuid4(),
        metadata={"test_key": "test_value"}
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    return deal

@pytest.fixture
async def mock_websocket():
    """Create a mock WebSocket for testing."""
    return MockWebSocket()

@pytest.fixture
async def connection_manager():
    """Get the WebSocket connection manager."""
    return get_connection_manager()

@pytest.mark.asyncio
@pytest.mark.integration
async def test_websocket_connection(connection_manager, mock_websocket, auth_override):
    """Test establishing a WebSocket connection."""
    # Connect the mock WebSocket
    user = await auth_override()
    await connection_manager.connect(mock_websocket, user.id)
    
    # Verify the connection was established
    assert mock_websocket.client_id in connection_manager.active_connections
    assert connection_manager.active_connections[mock_websocket.client_id]["user_id"] == user.id
    
    # Clean up
    await connection_manager.disconnect(mock_websocket)
    assert mock_websocket.client_id not in connection_manager.active_connections

@pytest.mark.asyncio
@pytest.mark.integration
async def test_deal_update_notification(connection_manager, mock_websocket, authenticated_client, 
                                        sample_deal, auth_override):
    """Test receiving deal update notifications via WebSocket."""
    # Connect the mock WebSocket
    user = await auth_override()
    await connection_manager.connect(mock_websocket, user.id)
    
    # Subscribe to deal updates
    await connection_manager.subscribe_to_deal(mock_websocket, str(sample_deal.id))
    
    # Update the deal via API
    update_data = {
        "title": "Updated Deal Title",
        "status": DealStatus.ACTIVE.value
    }
    
    # Create a task to listen for WebSocket messages
    async def listen_for_messages():
        try:
            message = await asyncio.wait_for(mock_websocket.receive_json(), timeout=2.0)
            return message
        except asyncio.TimeoutError:
            return None
    
    # Start listening for messages
    listen_task = asyncio.create_task(listen_for_messages())
    
    # Update the deal
    response = await authenticated_client.patch(
        f"/api/v1/deals/{sample_deal.id}",
        json=update_data
    )
    assert response.status_code == 200
    
    # Wait for the WebSocket message
    message = await listen_task
    
    # Verify we received a notification about the deal update
    assert message is not None
    assert message["type"] == "deal_update"
    assert message["data"]["id"] == str(sample_deal.id)
    assert message["data"]["title"] == update_data["title"]
    assert message["data"]["status"] == update_data["status"].lower()
    
    # Clean up
    await connection_manager.disconnect(mock_websocket)

@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_clients_notification(connection_manager, authenticated_client, 
                                             sample_deal, auth_override):
    """Test notifications to multiple WebSocket clients."""
    # Create multiple mock WebSockets
    mock_websocket1 = MockWebSocket()
    mock_websocket2 = MockWebSocket()
    mock_websocket3 = MockWebSocket()
    
    # Connect all WebSockets
    user = await auth_override()
    await connection_manager.connect(mock_websocket1, user.id)
    await connection_manager.connect(mock_websocket2, user.id)
    await connection_manager.connect(mock_websocket3, user.id)
    
    # Subscribe WebSockets 1 and 2 to the deal, but not 3
    await connection_manager.subscribe_to_deal(mock_websocket1, str(sample_deal.id))
    await connection_manager.subscribe_to_deal(mock_websocket2, str(sample_deal.id))
    
    # Update the deal
    update_data = {
        "title": "Multi-Client Test",
        "status": DealStatus.ACTIVE.value
    }
    
    # Create tasks to listen for WebSocket messages
    async def listen_for_messages(websocket):
        try:
            message = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
            return message
        except asyncio.TimeoutError:
            return None
    
    # Start listening for messages on all WebSockets
    listen_task1 = asyncio.create_task(listen_for_messages(mock_websocket1))
    listen_task2 = asyncio.create_task(listen_for_messages(mock_websocket2))
    listen_task3 = asyncio.create_task(listen_for_messages(mock_websocket3))
    
    # Update the deal
    response = await authenticated_client.patch(
        f"/api/v1/deals/{sample_deal.id}",
        json=update_data
    )
    assert response.status_code == 200
    
    # Wait for the WebSocket messages
    message1 = await listen_task1
    message2 = await listen_task2
    message3 = await listen_task3
    
    # Verify WebSockets 1 and 2 received notifications
    assert message1 is not None
    assert message1["type"] == "deal_update"
    assert message1["data"]["id"] == str(sample_deal.id)
    
    assert message2 is not None
    assert message2["type"] == "deal_update"
    assert message2["data"]["id"] == str(sample_deal.id)
    
    # Verify WebSocket 3 did not receive a notification
    assert message3 is None
    
    # Clean up
    await connection_manager.disconnect(mock_websocket1)
    await connection_manager.disconnect(mock_websocket2)
    await connection_manager.disconnect(mock_websocket3)

@pytest.mark.asyncio
@pytest.mark.integration
async def test_unsubscribe_from_deal(connection_manager, mock_websocket, authenticated_client, 
                                     sample_deal, auth_override):
    """Test unsubscribing from deal updates."""
    # Connect the mock WebSocket
    user = await auth_override()
    await connection_manager.connect(mock_websocket, user.id)
    
    # Subscribe to deal updates
    await connection_manager.subscribe_to_deal(mock_websocket, str(sample_deal.id))
    
    # Unsubscribe from deal updates
    await connection_manager.unsubscribe_from_deal(mock_websocket, str(sample_deal.id))
    
    # Update the deal
    update_data = {
        "title": "Unsubscribe Test",
        "status": DealStatus.ACTIVE.value
    }
    
    # Create a task to listen for WebSocket messages
    async def listen_for_messages():
        try:
            message = await asyncio.wait_for(mock_websocket.receive_json(), timeout=1.0)
            return message
        except asyncio.TimeoutError:
            return None
    
    # Start listening for messages
    listen_task = asyncio.create_task(listen_for_messages())
    
    # Update the deal
    response = await authenticated_client.patch(
        f"/api/v1/deals/{sample_deal.id}",
        json=update_data
    )
    assert response.status_code == 200
    
    # Wait for the WebSocket message
    message = await listen_task
    
    # Verify we did not receive a notification after unsubscribing
    assert message is None
    
    # Clean up
    await connection_manager.disconnect(mock_websocket)

@pytest.mark.asyncio
@pytest.mark.integration
async def test_websocket_authentication(app, connection_manager):
    """Test WebSocket authentication requirements."""
    # Create a mock WebSocket
    mock_websocket = MockWebSocket()
    
    # Try to connect without authentication
    # This should be handled by the WebSocket endpoint's dependency
    # For testing purposes, we'll simulate the authentication failure
    
    # In a real application, the WebSocket endpoint would handle authentication
    # and reject the connection if authentication fails
    
    # For this test, we'll verify that the connection manager properly
    # handles user_id being required for connections
    
    # Try to connect without a user_id (should raise an exception)
    with pytest.raises(ValueError, match="User ID is required"):
        await connection_manager.connect(mock_websocket, None)
    
    # Verify the connection was not established
    assert mock_websocket.client_id not in connection_manager.active_connections

@pytest.mark.asyncio
@pytest.mark.integration
async def test_websocket_disconnect_handling(connection_manager, mock_websocket, auth_override):
    """Test handling WebSocket disconnections."""
    # Connect the mock WebSocket
    user = await auth_override()
    await connection_manager.connect(mock_websocket, user.id)
    
    # Subscribe to a deal
    deal_id = str(uuid.uuid4())
    await connection_manager.subscribe_to_deal(mock_websocket, deal_id)
    
    # Verify the subscription
    assert deal_id in connection_manager.deal_subscriptions
    assert mock_websocket.client_id in connection_manager.deal_subscriptions[deal_id]
    
    # Simulate a client disconnect
    await connection_manager.disconnect(mock_websocket)
    
    # Verify the connection and subscriptions were cleaned up
    assert mock_websocket.client_id not in connection_manager.active_connections
    assert deal_id in connection_manager.deal_subscriptions
    assert mock_websocket.client_id not in connection_manager.deal_subscriptions[deal_id]

@pytest.mark.asyncio
@pytest.mark.integration
async def test_broadcast_to_all_clients(connection_manager, auth_override):
    """Test broadcasting messages to all connected clients."""
    # Create multiple mock WebSockets
    mock_websocket1 = MockWebSocket()
    mock_websocket2 = MockWebSocket()
    mock_websocket3 = MockWebSocket()
    
    # Connect all WebSockets
    user = await auth_override()
    await connection_manager.connect(mock_websocket1, user.id)
    await connection_manager.connect(mock_websocket2, user.id)
    await connection_manager.connect(mock_websocket3, user.id)
    
    # Broadcast a message to all clients
    broadcast_message = {
        "type": "system_notification",
        "data": {
            "message": "System maintenance in 10 minutes",
            "severity": "info"
        }
    }
    
    await connection_manager.broadcast(broadcast_message)
    
    # Verify all clients received the message
    assert len(mock_websocket1.received_messages) == 1
    assert mock_websocket1.received_messages[0] == broadcast_message
    
    assert len(mock_websocket2.received_messages) == 1
    assert mock_websocket2.received_messages[0] == broadcast_message
    
    assert len(mock_websocket3.received_messages) == 1
    assert mock_websocket3.received_messages[0] == broadcast_message
    
    # Clean up
    await connection_manager.disconnect(mock_websocket1)
    await connection_manager.disconnect(mock_websocket2)
    await connection_manager.disconnect(mock_websocket3) 