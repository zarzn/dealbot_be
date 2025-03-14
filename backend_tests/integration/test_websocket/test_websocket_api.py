"""Tests for the WebSocket API functionality."""

import asyncio
import json
import pytest
from typing import Dict, Any, List, Optional

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient

from core.services.websocket import get_connection_manager

class MockWebSocket:
    """Mock WebSocket client for testing."""
    
    def __init__(self):
        """Initialize the mock WebSocket."""
        self.client_id = f"test-client-{id(self)}"
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.received_messages = []
        self.sent_messages = []
        
    async def receive_text(self) -> str:
        """Simulate receiving a message from the WebSocket."""
        if not self.received_messages:
            raise WebSocketDisconnect(code=1000)
        return self.received_messages.pop(0)
        
    async def receive_json(self) -> Dict[str, Any]:
        """Simulate receiving a JSON message from the WebSocket."""
        if not self.received_messages:
            raise WebSocketDisconnect(code=self.close_code or 1000)
        return json.loads(self.received_messages.pop(0))
        
    async def send_text(self, data: str):
        """Simulate sending a message to the WebSocket."""
        if self.closed:
            raise WebSocketDisconnect(code=1000)
        self.sent_messages.append(data)
        
    async def send_json(self, data: Dict[str, Any]):
        """Simulate sending a JSON message to the WebSocket."""
        await self.send_text(json.dumps(data))
        
    async def close(self, code: int = 1000, reason: str = ""):
        """Simulate closing the WebSocket connection."""
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        
    async def accept(self):
        """Simulate accepting the WebSocket connection."""
        self.accepted = True
        
    def add_message(self, message: Dict[str, Any]):
        """Add a message to the received messages queue."""
        self.received_messages.append(json.dumps(message))

@pytest.fixture
async def mock_websocket():
    """Create a mock WebSocket for testing."""
    return MockWebSocket()

@pytest.fixture
def connection_manager():
    """Get the WebSocket connection manager."""
    return get_connection_manager()

@pytest.mark.asyncio
async def test_websocket_connection(connection_manager, mock_websocket):
    """Test establishing a WebSocket connection."""
    # Connect the mock WebSocket
    connection_id = await connection_manager.connect(mock_websocket, "test-user")
    
    # Verify the connection was established
    assert connection_id in connection_manager.active_connections
    assert connection_manager.connection_data[connection_id]["user_id"] == "test-user"
    
    # Disconnect the WebSocket
    await connection_manager.disconnect(connection_id)
    assert connection_id not in connection_manager.active_connections

@pytest.mark.asyncio
async def test_personal_message(connection_manager, mock_websocket):
    """Test sending a personal message to a WebSocket client."""
    # Connect the mock WebSocket
    connection_id = await connection_manager.connect(mock_websocket, "test-user")
    
    # Send a personal message
    test_message = {"action": "test", "data": "Hello, world!"}
    await connection_manager.send_personal_message(test_message, connection_id)
    
    # Verify the message was sent
    assert len(mock_websocket.sent_messages) == 1
    sent_message = json.loads(mock_websocket.sent_messages[0])
    assert sent_message["action"] == "test"
    assert sent_message["data"] == "Hello, world!"
    
    # Disconnect the WebSocket
    await connection_manager.disconnect(connection_id)

@pytest.mark.asyncio
async def test_broadcast(connection_manager):
    """Test broadcasting a message to all WebSocket clients."""
    # Create multiple mock WebSockets
    mock_websocket1 = MockWebSocket()
    mock_websocket2 = MockWebSocket()
    mock_websocket3 = MockWebSocket()
    
    # Connect all WebSockets
    connection_id1 = await connection_manager.connect(mock_websocket1, "user1")
    connection_id2 = await connection_manager.connect(mock_websocket2, "user2")
    connection_id3 = await connection_manager.connect(mock_websocket3, "user3")
    
    # Broadcast a message
    test_message = {"action": "broadcast", "data": "Hello, everyone!"}
    await connection_manager.broadcast(test_message)
    
    # Verify all WebSockets received the message
    for websocket in [mock_websocket1, mock_websocket2, mock_websocket3]:
        assert len(websocket.sent_messages) == 1
        sent_message = json.loads(websocket.sent_messages[0])
        assert sent_message["action"] == "broadcast"
        assert sent_message["data"] == "Hello, everyone!"
    
    # Disconnect all WebSockets
    await connection_manager.disconnect(connection_id1)
    await connection_manager.disconnect(connection_id2)
    await connection_manager.disconnect(connection_id3)

@pytest.mark.asyncio
async def test_room_messaging(connection_manager):
    """Test room-based messaging."""
    # Create multiple mock WebSockets
    mock_websocket1 = MockWebSocket()
    mock_websocket2 = MockWebSocket()
    mock_websocket3 = MockWebSocket()
    
    # Connect all WebSockets
    connection_id1 = await connection_manager.connect(mock_websocket1, "user1")
    connection_id2 = await connection_manager.connect(mock_websocket2, "user2")
    connection_id3 = await connection_manager.connect(mock_websocket3, "user3")
    
    # Join room1 with websocket1 and websocket2, but not websocket3
    room_id = "room1"
    await connection_manager.join_room(connection_id1, room_id)
    await connection_manager.join_room(connection_id2, room_id)
    
    # Broadcast a message to room1
    test_message = {"action": "roomMessage", "data": "Hello, room1!"}
    await connection_manager.broadcast_to_room(room_id, test_message)
    
    # Verify websocket1 and websocket2 received the message, but not websocket3
    for websocket in [mock_websocket1, mock_websocket2]:
        assert len(websocket.sent_messages) == 1
        sent_message = json.loads(websocket.sent_messages[0])
        assert sent_message["action"] == "roomMessage"
        assert sent_message["data"] == "Hello, room1!"
    
    assert len(mock_websocket3.sent_messages) == 0
    
    # Leave room1 with websocket1
    await connection_manager.leave_room(connection_id1, room_id)
    
    # Clear sent messages
    mock_websocket1.sent_messages = []
    mock_websocket2.sent_messages = []
    
    # Broadcast another message to room1
    test_message = {"action": "roomMessage", "data": "Hello again, room1!"}
    await connection_manager.broadcast_to_room(room_id, test_message)
    
    # Verify only websocket2 received the message
    assert len(mock_websocket1.sent_messages) == 0
    assert len(mock_websocket2.sent_messages) == 1
    sent_message = json.loads(mock_websocket2.sent_messages[0])
    assert sent_message["action"] == "roomMessage"
    assert sent_message["data"] == "Hello again, room1!"
    
    # Disconnect all WebSockets
    await connection_manager.disconnect(connection_id1)
    await connection_manager.disconnect(connection_id2)
    await connection_manager.disconnect(connection_id3)

@pytest.mark.asyncio
async def test_topic_subscription(connection_manager):
    """Test topic-based subscription and messaging."""
    # Create multiple mock WebSockets
    mock_websocket1 = MockWebSocket()
    mock_websocket2 = MockWebSocket()
    mock_websocket3 = MockWebSocket()
    
    # Connect all WebSockets
    connection_id1 = await connection_manager.connect(mock_websocket1, "user1")
    connection_id2 = await connection_manager.connect(mock_websocket2, "user2")
    connection_id3 = await connection_manager.connect(mock_websocket3, "user3")
    
    # Subscribe to topic1 with websocket1 and websocket2, but not websocket3
    topic = "topic1"
    await connection_manager.subscribe_to_topic(connection_id1, topic)
    await connection_manager.subscribe_to_topic(connection_id2, topic)
    
    # Broadcast a message to topic1
    test_message = {"action": "topicMessage", "data": "Hello, topic1!"}
    await connection_manager.broadcast_to_topic(topic, test_message)
    
    # Verify websocket1 and websocket2 received the message, but not websocket3
    for websocket in [mock_websocket1, mock_websocket2]:
        assert len(websocket.sent_messages) == 1
        sent_message = json.loads(websocket.sent_messages[0])
        assert sent_message["action"] == "topicMessage"
        assert sent_message["data"] == "Hello, topic1!"
    
    assert len(mock_websocket3.sent_messages) == 0
    
    # Unsubscribe from topic1 with websocket1
    await connection_manager.unsubscribe_from_topic(connection_id1, topic)
    
    # Clear sent messages
    mock_websocket1.sent_messages = []
    mock_websocket2.sent_messages = []
    
    # Broadcast another message to topic1
    test_message = {"action": "topicMessage", "data": "Hello again, topic1!"}
    await connection_manager.broadcast_to_topic(topic, test_message)
    
    # Verify only websocket2 received the message
    assert len(mock_websocket1.sent_messages) == 0
    assert len(mock_websocket2.sent_messages) == 1
    sent_message = json.loads(mock_websocket2.sent_messages[0])
    assert sent_message["action"] == "topicMessage"
    assert sent_message["data"] == "Hello again, topic1!"
    
    # Disconnect all WebSockets
    await connection_manager.disconnect(connection_id1)
    await connection_manager.disconnect(connection_id2)
    await connection_manager.disconnect(connection_id3)

@pytest.mark.asyncio
async def test_websocket_disconnect_handling(connection_manager):
    """Test handling WebSocket disconnections."""
    # Create a mock WebSocket
    mock_websocket = MockWebSocket()
    
    # Connect the mock WebSocket
    connection_id = await connection_manager.connect(mock_websocket, "test-user")
    
    # Join a room and subscribe to a topic
    room_id = "test-room"
    topic = "test-topic"
    await connection_manager.join_room(connection_id, room_id)
    await connection_manager.subscribe_to_topic(connection_id, topic)
    
    # Verify the connection is in the room and subscribed to the topic
    assert connection_id in connection_manager.room_members.get(room_id, set())
    assert connection_id in connection_manager.topic_subscribers.get(topic, set())
    
    # Disconnect the WebSocket
    await connection_manager.disconnect(connection_id)
    
    # Verify the connection is removed from the room and topic
    assert connection_id not in connection_manager.active_connections
    assert connection_id not in connection_manager.room_members.get(room_id, set())
    assert connection_id not in connection_manager.topic_subscribers.get(topic, set()) 