"""
WebSocket API for Agentic Deals System

This module provides WebSocket endpoints for real-time communication.
"""

import json
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, Header
from pydantic import BaseModel, Field

from core.services.websocket import get_connection_manager
from core.services.auth import verify_token
from core.utils.logger import get_logger
from core.exceptions import AuthenticationError

router = APIRouter()
logger = get_logger(__name__)

class WebSocketMessage(BaseModel):
    """Base model for WebSocket messages."""
    action: str = Field(..., description="The action to perform")
    
    class Config:
        extra = "allow"

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """
    WebSocket endpoint for real-time communication.
    
    Args:
        websocket: The WebSocket connection
        token: Optional authentication token as query parameter
        authorization: Optional authentication token in Authorization header
    """
    # Get connection manager
    connection_manager = get_connection_manager()
    
    # Extract token from Authorization header if provided
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    
    # Authenticate user if token is provided
    user_id = None
    if token:
        try:
            payload = verify_token(token)
            user_id = payload.get("sub")
        except AuthenticationError as e:
            logger.warning(f"WebSocket authentication failed: {str(e)}")
            await websocket.close(code=1008, reason="Authentication failed")
            return
    
    # Accept connection
    connection_id = await connection_manager.connect(websocket, user_id)
    
    try:
        # Send welcome message
        await connection_manager.send_personal_message(
            {
                "action": "connected",
                "message": "Connected to WebSocket API",
                "connection_id": connection_id,
                "user_id": user_id
            },
            connection_id
        )
        
        # Process messages
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            try:
                # Parse message
                message_data = json.loads(data)
                action = message_data.get("action")
                
                if not action:
                    await connection_manager.send_personal_message(
                        {
                            "action": "error",
                            "message": "Missing action field"
                        },
                        connection_id
                    )
                    continue
                
                # Process message based on action
                await process_message(connection_manager, connection_id, user_id, action, message_data)
                
            except json.JSONDecodeError:
                await connection_manager.send_personal_message(
                    {
                        "action": "error",
                        "message": "Invalid JSON format"
                    },
                    connection_id
                )
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")
                await connection_manager.send_personal_message(
                    {
                        "action": "error",
                        "message": f"Error processing message: {str(e)}"
                    },
                    connection_id
                )
    
    except WebSocketDisconnect:
        # Handle disconnection
        await connection_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await connection_manager.disconnect(connection_id)

async def process_message(
    connection_manager,
    connection_id: str,
    user_id: Optional[str],
    action: str,
    message_data: Dict[str, Any]
):
    """
    Process a WebSocket message based on its action.
    
    Args:
        connection_manager: The connection manager
        connection_id: The connection ID
        user_id: The user ID (if authenticated)
        action: The action to perform
        message_data: The message data
    """
    # Handle different actions
    if action == "ping":
        await connection_manager.send_personal_message(
            {
                "action": "pong",
                "timestamp": message_data.get("timestamp")
            },
            connection_id
        )
    
    elif action == "sendMessage":
        # Check if user is authenticated for certain operations
        if not user_id and message_data.get("requireAuth", False):
            await connection_manager.send_personal_message(
                {
                    "action": "error",
                    "message": "Authentication required"
                },
                connection_id
            )
            return
        
        # Get message data
        data = message_data.get("data")
        room_id = message_data.get("room")
        
        if not data:
            await connection_manager.send_personal_message(
                {
                    "action": "error",
                    "message": "Missing data field"
                },
                connection_id
            )
            return
        
        # Broadcast to room if specified, otherwise broadcast to all
        if room_id:
            await connection_manager.broadcast_to_room(
                room_id,
                {
                    "action": "messageResponse",
                    "sender": user_id,
                    "data": data,
                    "room": room_id,
                    "timestamp": message_data.get("timestamp")
                }
            )
        else:
            await connection_manager.broadcast(
                {
                    "action": "messageResponse",
                    "sender": user_id,
                    "data": data,
                    "timestamp": message_data.get("timestamp")
                }
            )
        
        # Send confirmation to sender
        await connection_manager.send_personal_message(
            {
                "action": "messageSent",
                "message": "Message sent successfully",
                "data": data,
                "room": room_id,
                "timestamp": message_data.get("timestamp")
            },
            connection_id
        )
    
    elif action == "subscribe":
        # Get topic
        topic = message_data.get("topic")
        
        if not topic:
            await connection_manager.send_personal_message(
                {
                    "action": "error",
                    "message": "Missing topic field"
                },
                connection_id
            )
            return
        
        # Subscribe to topic
        success = await connection_manager.subscribe_to_topic(connection_id, topic)
        
        # Send confirmation
        await connection_manager.send_personal_message(
            {
                "action": "subscribeResponse",
                "success": success,
                "topic": topic,
                "message": "Subscribed to topic" if success else "Failed to subscribe to topic"
            },
            connection_id
        )
    
    elif action == "unsubscribe":
        # Get topic
        topic = message_data.get("topic")
        
        if not topic:
            await connection_manager.send_personal_message(
                {
                    "action": "error",
                    "message": "Missing topic field"
                },
                connection_id
            )
            return
        
        # Unsubscribe from topic
        success = await connection_manager.unsubscribe_from_topic(connection_id, topic)
        
        # Send confirmation
        await connection_manager.send_personal_message(
            {
                "action": "unsubscribeResponse",
                "success": success,
                "topic": topic,
                "message": "Unsubscribed from topic" if success else "Failed to unsubscribe from topic"
            },
            connection_id
        )
    
    elif action == "joinRoom":
        # Get room ID
        room_id = message_data.get("roomId")
        
        if not room_id:
            await connection_manager.send_personal_message(
                {
                    "action": "error",
                    "message": "Missing roomId field"
                },
                connection_id
            )
            return
        
        # Join room
        success = await connection_manager.join_room(connection_id, room_id)
        
        # Send confirmation
        await connection_manager.send_personal_message(
            {
                "action": "roomJoined",
                "success": success,
                "roomId": room_id,
                "message": "Joined room successfully" if success else "Failed to join room"
            },
            connection_id
        )
        
        # Notify room members
        if success:
            await connection_manager.broadcast_to_room(
                room_id,
                {
                    "action": "userJoined",
                    "userId": user_id,
                    "roomId": room_id,
                    "timestamp": message_data.get("timestamp")
                }
            )
    
    elif action == "leaveRoom":
        # Get room ID
        room_id = message_data.get("roomId")
        
        if not room_id:
            await connection_manager.send_personal_message(
                {
                    "action": "error",
                    "message": "Missing roomId field"
                },
                connection_id
            )
            return
        
        # Leave room
        success = await connection_manager.leave_room(connection_id, room_id)
        
        # Send confirmation
        await connection_manager.send_personal_message(
            {
                "action": "roomLeft",
                "success": success,
                "roomId": room_id,
                "message": "Left room successfully" if success else "Failed to leave room"
            },
            connection_id
        )
        
        # Notify room members
        if success:
            await connection_manager.broadcast_to_room(
                room_id,
                {
                    "action": "userLeft",
                    "userId": user_id,
                    "roomId": room_id,
                    "timestamp": message_data.get("timestamp")
                }
            )
    
    elif action == "getPriceUpdate":
        # Get symbol
        symbol = message_data.get("symbol")
        
        if not symbol:
            await connection_manager.send_personal_message(
                {
                    "action": "error",
                    "message": "Missing symbol field"
                },
                connection_id
            )
            return
        
        # Mock price update for now
        # In production, this would fetch real data
        await connection_manager.send_personal_message(
            {
                "action": "priceUpdate",
                "symbol": symbol,
                "data": {
                    "price": 123.45,
                    "change": 2.5,
                    "timestamp": message_data.get("timestamp")
                }
            },
            connection_id
        )
    
    elif action == "getNotification":
        # Mock notification for now
        # In production, this would fetch real notifications
        await connection_manager.send_personal_message(
            {
                "action": "notification",
                "data": {
                    "id": "notif-123",
                    "type": "alert",
                    "message": "New deal available",
                    "timestamp": message_data.get("timestamp")
                }
            },
            connection_id
        )
    
    else:
        # Unknown action
        await connection_manager.send_personal_message(
            {
                "action": "error",
                "message": f"Unknown action: {action}"
            },
            connection_id
        ) 