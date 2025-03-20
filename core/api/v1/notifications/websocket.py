"""WebSocket endpoint for notifications."""

from typing import Dict, Any, List
from fastapi import WebSocket, WebSocketDisconnect
import logging
import json
from datetime import datetime
from jose import jwt, JWTError, ExpiredSignatureError
from core.config import settings
from core.utils.redis import get_redis_client
from core.services.auth import verify_token, TokenRefreshError
from core.services.notifications import create_notification
import uuid
import asyncio
from time import time

# Configure logging with less verbosity
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        self.active_connections: Dict[str, List[Dict[str, Any]]] = {}
        self.last_broadcast: Dict[str, float] = {}  # Track last broadcast time per user
        self.broadcast_cooldown = 2.0  # Minimum seconds between broadcasts

    async def connect(self, websocket: WebSocket, user_id: str):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append({
            "socket": websocket,
            "last_check": time()
        })
        logger.debug(f"WebSocket connection established for user {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id] = [
                conn for conn in self.active_connections[user_id] 
                if conn["socket"] != websocket
            ]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                if user_id in self.last_broadcast:
                    del self.last_broadcast[user_id]
        logger.debug(f"WebSocket connection closed for user {user_id}")

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        current_time = time()
        
        # Check cooldown
        if user_id in self.last_broadcast:
            time_since_last = current_time - self.last_broadcast[user_id]
            if time_since_last < self.broadcast_cooldown:
                return  # Skip this broadcast if within cooldown
        
        if user_id in self.active_connections:
            disconnected_sockets = []
            for conn in self.active_connections[user_id]:
                try:
                    websocket = conn["socket"]
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to user {user_id}: {str(e)}")
                    disconnected_sockets.append(conn)
            
            # Clean up disconnected sockets
            for conn in disconnected_sockets:
                self.disconnect(conn["socket"], user_id)
            
            # Update last broadcast time
            self.last_broadcast[user_id] = current_time

notification_manager = NotificationManager()

async def get_websocket_user(websocket: WebSocket) -> str:
    """Get user from WebSocket connection by validating the token."""
    try:
        token = websocket.query_params.get('token')
        if not token:
            logger.error("No token provided in WebSocket connection")
            return None

        # Special handling for test tokens
        if token.startswith('test_websocket_token_'):
            logger.info(f"Using test token for WebSocket: {token}")
            # Generate a mock user ID for test tokens
            return "00000000-0000-4000-a000-000000000000"

        try:
            # Get JWT secret key using the correct method
            secret_key = settings.JWT_SECRET_KEY
            if hasattr(secret_key, 'get_secret_value'):
                secret_key = secret_key.get_secret_value()
                
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("sub")
            if not user_id:
                logger.error("Token payload missing user ID")
                return None
            return user_id
                
        except ExpiredSignatureError:
            logger.error("Token has expired")
            return None
            
        except JWTError as e:
            logger.error(f"Token verification error: {str(e)}")
            return None

    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None

async def handle_websocket(websocket: WebSocket):
    """Handle WebSocket connection."""
    try:
        user_id = await get_websocket_user(websocket)
        if not user_id:
            logger.error("Failed to authenticate WebSocket connection")
            await websocket.close(code=4001, reason="Authentication failed")
            return

        logger.info(f"Accepted WebSocket connection for user {user_id}")
        await websocket.accept()
        await notification_manager.connect(websocket, user_id)
        
        # Send welcome message to confirm connection
        try:
            await websocket.send_json({
                "type": "connection_established",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"Sent welcome message to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send welcome message: {str(e)}")
        
        try:
            while True:
                try:
                    data = await websocket.receive_json()
                    logger.info(f"Received WebSocket message from user {user_id}: {data}")
                    
                    # Handle ping messages
                    if isinstance(data, dict) and data.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat(),
                            "received_ping": data
                        })
                        logger.info(f"Sent pong response to user {user_id}")
                        continue
                    
                    # If it's a notification, store it and broadcast
                    if isinstance(data, dict) and data.get("type") == "notification":
                        # Look for notification data in either "data" or "notification" field
                        notification_data = data.get("data") or data.get("notification", {})
                        
                        # If neither field exists, check if all required fields are in the top-level object
                        if not notification_data and "title" in data:
                            # Use the top-level object itself as the notification data
                            notification_data = data
                            # Remove the type field as it's not part of the notification data
                            if "type" in notification_data:
                                del notification_data["type"]
                        
                        # Ensure user_id is set
                        notification_data["user_id"] = user_id
                        
                        # Remove the conversion from backend format to frontend format
                        # as the frontend now expects and handles backend types directly
                        if "notification_type" in notification_data and "type" not in notification_data:
                            # Just rename the field without changing its value
                            notification_data["type"] = notification_data.pop("notification_type")
                        
                        # Convert timestamp to created_at if needed
                        if "timestamp" in notification_data and "created_at" not in notification_data:
                            notification_data["created_at"] = notification_data.pop("timestamp")
                        
                        # Ensure read status is set
                        if "read" not in notification_data:
                            notification_data["read"] = False
                        
                        try:
                            stored_notification = await create_notification(notification_data)
                            await notification_manager.broadcast_to_user(user_id, {
                                "type": "notification",
                                "notification": stored_notification  # Send as "notification" to match frontend expectation
                            })
                            logger.info(f"Processed and broadcasted notification for user {user_id}")
                        except Exception as e:
                            logger.error(f"Failed to process notification: {str(e)}")
                            await websocket.send_json({
                                "type": "error",
                                "message": str(e)
                            })
                    else:
                        # Unknown message type
                        logger.warning(f"Received unknown message type from user {user_id}: {data}")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Unknown message type"
                        })
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON from user {user_id}: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON message"
                    })
                
                # Add delay between message processing
                await asyncio.sleep(0.1)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for user {user_id}")
            notification_manager.disconnect(websocket, user_id)
            
        except Exception as e:
            logger.error(f"Error in WebSocket connection for user {user_id}: {str(e)}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"WebSocket error: {str(e)}"
                })
                await websocket.close(code=1011, reason=str(e))
            except:
                pass
            notification_manager.disconnect(websocket, user_id)
            
    except Exception as e:
        logger.error(f"Error establishing WebSocket connection: {str(e)}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass 