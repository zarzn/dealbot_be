"""
WebSocket Service for Agentic Deals System

This module provides functionality for managing WebSocket connections and messages.
It handles connection tracking, message broadcasting, and subscription management.
"""

import json
import logging
import uuid
from typing import Dict, List, Optional, Any, Set

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.services.redis import get_redis_service
from core.utils.logger import get_logger

logger = get_logger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections, including connection tracking,
    message broadcasting, and subscription management.
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self.topic_subscribers: Dict[str, Set[str]] = {}  # topic -> set of connection_ids
        self.room_members: Dict[str, Set[str]] = {}  # room_id -> set of connection_ids
        self.connection_data: Dict[str, Dict[str, Any]] = {}  # connection_id -> metadata
        self.redis_service = get_redis_service()
    
    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None) -> str:
        """
        Accept a WebSocket connection and store it.
        
        Args:
            websocket: The WebSocket connection
            user_id: Optional user ID for authenticated connections
            
        Returns:
            str: The connection ID
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        
        # Store connection metadata
        self.connection_data[connection_id] = {
            "user_id": user_id,
            "connected_at": str(datetime.now()),
            "topics": set(),
            "rooms": set()
        }
        
        # Associate connection with user if authenticated
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            
            # Store in Redis for distributed systems
            await self.redis_service.sadd(f"websocket:user:{user_id}", connection_id)
        
        # Store connection in Redis
        await self.redis_service.set(
            f"websocket:connection:{connection_id}",
            json.dumps({
                "user_id": user_id,
                "connected_at": self.connection_data[connection_id]["connected_at"]
            }),
            expire=86400  # 24 hours
        )
        
        logger.info(f"WebSocket connected: {connection_id} (User: {user_id})")
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """
        Handle disconnection of a WebSocket.
        
        Args:
            connection_id: The ID of the connection to disconnect
        """
        if connection_id not in self.active_connections:
            return
        
        # Get user ID before removing connection
        user_id = self.connection_data.get(connection_id, {}).get("user_id")
        
        # Remove from active connections
        del self.active_connections[connection_id]
        
        # Remove from user connections
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
            
            # Remove from Redis
            await self.redis_service.srem(f"websocket:user:{user_id}", connection_id)
        
        # Remove from topics
        for topic in list(self.topic_subscribers.keys()):
            if connection_id in self.topic_subscribers[topic]:
                self.topic_subscribers[topic].discard(connection_id)
                if not self.topic_subscribers[topic]:
                    del self.topic_subscribers[topic]
                
                # Remove from Redis
                await self.redis_service.srem(f"websocket:topic:{topic}", connection_id)
        
        # Remove from rooms
        for room_id in list(self.room_members.keys()):
            if connection_id in self.room_members[room_id]:
                self.room_members[room_id].discard(connection_id)
                if not self.room_members[room_id]:
                    del self.room_members[room_id]
                
                # Remove from Redis
                await self.redis_service.srem(f"websocket:room:{room_id}", connection_id)
        
        # Remove connection data
        if connection_id in self.connection_data:
            del self.connection_data[connection_id]
        
        # Remove from Redis
        await self.redis_service.delete(f"websocket:connection:{connection_id}")
        
        logger.info(f"WebSocket disconnected: {connection_id} (User: {user_id})")
    
    async def send_personal_message(self, message: Dict[str, Any], connection_id: str):
        """
        Send a message to a specific connection.
        
        Args:
            message: The message to send
            connection_id: The connection ID to send to
        """
        if connection_id not in self.active_connections:
            logger.warning(f"Attempted to send message to non-existent connection: {connection_id}")
            return
        
        websocket = self.active_connections[connection_id]
        await websocket.send_text(json.dumps(message))
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
        """
        disconnected = []
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {str(e)}")
                disconnected.append(connection_id)
        
        # Clean up any disconnected clients
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    async def broadcast_to_topic(self, topic: str, message: Dict[str, Any]):
        """
        Broadcast a message to all subscribers of a topic.
        
        Args:
            topic: The topic to broadcast to
            message: The message to broadcast
        """
        if topic not in self.topic_subscribers:
            logger.warning(f"Attempted to broadcast to non-existent topic: {topic}")
            return
        
        disconnected = []
        for connection_id in self.topic_subscribers[topic]:
            if connection_id in self.active_connections:
                try:
                    await self.active_connections[connection_id].send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending message to {connection_id}: {str(e)}")
                    disconnected.append(connection_id)
            else:
                disconnected.append(connection_id)
        
        # Clean up any disconnected clients
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """
        Broadcast a message to all connections of a user.
        
        Args:
            user_id: The user ID to broadcast to
            message: The message to broadcast
        """
        if user_id not in self.user_connections:
            logger.warning(f"Attempted to broadcast to non-existent user: {user_id}")
            return
        
        disconnected = []
        for connection_id in self.user_connections[user_id]:
            if connection_id in self.active_connections:
                try:
                    await self.active_connections[connection_id].send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending message to {connection_id}: {str(e)}")
                    disconnected.append(connection_id)
            else:
                disconnected.append(connection_id)
        
        # Clean up any disconnected clients
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any]):
        """
        Broadcast a message to all members of a room.
        
        Args:
            room_id: The room ID to broadcast to
            message: The message to broadcast
        """
        if room_id not in self.room_members:
            logger.warning(f"Attempted to broadcast to non-existent room: {room_id}")
            return
        
        disconnected = []
        for connection_id in self.room_members[room_id]:
            if connection_id in self.active_connections:
                try:
                    await self.active_connections[connection_id].send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending message to {connection_id}: {str(e)}")
                    disconnected.append(connection_id)
            else:
                disconnected.append(connection_id)
        
        # Clean up any disconnected clients
        for connection_id in disconnected:
            await self.disconnect(connection_id)
    
    async def subscribe_to_topic(self, connection_id: str, topic: str):
        """
        Subscribe a connection to a topic.
        
        Args:
            connection_id: The connection ID to subscribe
            topic: The topic to subscribe to
        """
        if connection_id not in self.active_connections:
            logger.warning(f"Attempted to subscribe non-existent connection: {connection_id}")
            return False
        
        if topic not in self.topic_subscribers:
            self.topic_subscribers[topic] = set()
        
        self.topic_subscribers[topic].add(connection_id)
        
        # Update connection data
        if connection_id in self.connection_data:
            self.connection_data[connection_id]["topics"].add(topic)
        
        # Store in Redis
        await self.redis_service.sadd(f"websocket:topic:{topic}", connection_id)
        
        logger.info(f"Connection {connection_id} subscribed to topic: {topic}")
        return True
    
    async def unsubscribe_from_topic(self, connection_id: str, topic: str):
        """
        Unsubscribe a connection from a topic.
        
        Args:
            connection_id: The connection ID to unsubscribe
            topic: The topic to unsubscribe from
        """
        if topic not in self.topic_subscribers:
            logger.warning(f"Attempted to unsubscribe from non-existent topic: {topic}")
            return False
        
        if connection_id not in self.topic_subscribers[topic]:
            logger.warning(f"Connection {connection_id} not subscribed to topic: {topic}")
            return False
        
        self.topic_subscribers[topic].discard(connection_id)
        
        # Clean up empty topics
        if not self.topic_subscribers[topic]:
            del self.topic_subscribers[topic]
        
        # Update connection data
        if connection_id in self.connection_data:
            self.connection_data[connection_id]["topics"].discard(topic)
        
        # Remove from Redis
        await self.redis_service.srem(f"websocket:topic:{topic}", connection_id)
        
        logger.info(f"Connection {connection_id} unsubscribed from topic: {topic}")
        return True
    
    async def join_room(self, connection_id: str, room_id: str):
        """
        Add a connection to a room.
        
        Args:
            connection_id: The connection ID to add
            room_id: The room ID to join
        """
        if connection_id not in self.active_connections:
            logger.warning(f"Attempted to add non-existent connection to room: {connection_id}")
            return False
        
        if room_id not in self.room_members:
            self.room_members[room_id] = set()
        
        self.room_members[room_id].add(connection_id)
        
        # Update connection data
        if connection_id in self.connection_data:
            self.connection_data[connection_id]["rooms"].add(room_id)
        
        # Store in Redis
        await self.redis_service.sadd(f"websocket:room:{room_id}", connection_id)
        
        logger.info(f"Connection {connection_id} joined room: {room_id}")
        return True
    
    async def leave_room(self, connection_id: str, room_id: str):
        """
        Remove a connection from a room.
        
        Args:
            connection_id: The connection ID to remove
            room_id: The room ID to leave
        """
        if room_id not in self.room_members:
            logger.warning(f"Attempted to leave non-existent room: {room_id}")
            return False
        
        if connection_id not in self.room_members[room_id]:
            logger.warning(f"Connection {connection_id} not in room: {room_id}")
            return False
        
        self.room_members[room_id].discard(connection_id)
        
        # Clean up empty rooms
        if not self.room_members[room_id]:
            del self.room_members[room_id]
        
        # Update connection data
        if connection_id in self.connection_data:
            self.connection_data[connection_id]["rooms"].discard(room_id)
        
        # Remove from Redis
        await self.redis_service.srem(f"websocket:room:{room_id}", connection_id)
        
        logger.info(f"Connection {connection_id} left room: {room_id}")
        return True
    
    def get_connection_count(self) -> int:
        """
        Get the number of active connections.
        
        Returns:
            int: The number of active connections
        """
        return len(self.active_connections)
    
    def get_topic_subscriber_count(self, topic: str) -> int:
        """
        Get the number of subscribers to a topic.
        
        Args:
            topic: The topic to check
            
        Returns:
            int: The number of subscribers
        """
        if topic not in self.topic_subscribers:
            return 0
        return len(self.topic_subscribers[topic])
    
    def get_room_member_count(self, room_id: str) -> int:
        """
        Get the number of members in a room.
        
        Args:
            room_id: The room ID to check
            
        Returns:
            int: The number of members
        """
        if room_id not in self.room_members:
            return 0
        return len(self.room_members[room_id])


# Singleton instance
_connection_manager = None

def get_connection_manager() -> ConnectionManager:
    """
    Get the singleton instance of the connection manager.
    
    Returns:
        ConnectionManager: The connection manager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


# Missing import
from datetime import datetime 