"""WebSocket endpoint for notifications."""

from typing import Dict, Any, List
from fastapi import WebSocket, WebSocketDisconnect
import logging
import json
from datetime import datetime
import jwt
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

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY.get_secret_value(),
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("sub")
            if not user_id:
                logger.error("Token payload missing user ID")
                return None
            return user_id
                
        except jwt.ExpiredSignatureError:
            logger.error("Token has expired")
            return None
            
        except jwt.JWTError as e:
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
            await websocket.close(code=4001, reason="Authentication failed")
            return

        await websocket.accept()
        await notification_manager.connect(websocket, user_id)
        
        try:
            while True:
                data = await websocket.receive_json()
                
                # If it's a notification, store it and broadcast
                if isinstance(data, dict) and data.get("type") == "notification":
                    notification_data = data.get("data", {})
                    notification_data["user_id"] = user_id
                    
                    try:
                        stored_notification = await create_notification(notification_data)
                        await notification_manager.broadcast_to_user(user_id, {
                            "type": "notification",
                            "data": stored_notification
                        })
                    except Exception as e:
                        logger.error(f"Failed to process notification: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e)
                        })
                
                # Add delay between message processing
                await asyncio.sleep(0.1)
                
        except WebSocketDisconnect:
            notification_manager.disconnect(websocket, user_id)
            
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {str(e)}")
            await websocket.close(code=1011, reason=str(e))
            
    except Exception as e:
        logger.error(f"Error establishing WebSocket connection: {str(e)}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass 