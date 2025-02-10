"""WebSocket endpoint for notifications."""

from typing import Dict, Any, List
from fastapi import WebSocket, WebSocketDisconnect
import logging
import json
from datetime import datetime
import jwt
from core.config import settings
from core.utils.redis import get_redis_client
from core.services.auth import verify_token

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connection established for user {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket connection closed for user {user_id}")

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        if user_id in self.active_connections:
            disconnected_sockets = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to user {user_id}: {str(e)}")
                    disconnected_sockets.append(websocket)
            
            # Clean up disconnected sockets
            for websocket in disconnected_sockets:
                self.disconnect(websocket, user_id)

notification_manager = NotificationManager()

async def get_websocket_user(websocket: WebSocket) -> str:
    """Get user from WebSocket connection by validating the token."""
    try:
        # Get token from query parameters
        token = websocket.query_params.get('token')
        if not token:
            logger.error("No token provided in WebSocket connection")
            return None

        try:
            # Get Redis client for token verification
            redis = await get_redis_client()
            
            # Verify token using auth service
            try:
                payload = await verify_token(token, redis)
                if not payload:
                    logger.error("Invalid token")
                    return None
                    
                user_id = payload.get("sub")
                if not user_id:
                    logger.error("Token payload missing user ID")
                    return None
                    
                return user_id
                
            except Exception as e:
                logger.error(f"Token verification error: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"Redis error: {str(e)}")
            return None

    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None

async def handle_websocket(websocket: WebSocket):
    """Handle WebSocket connection."""
    try:
        # Get user ID from token before accepting the connection
        user_id = await get_websocket_user(websocket)
        if not user_id:
            logger.error("Authentication failed, rejecting WebSocket connection")
            await websocket.close(code=4001, reason="Authentication failed")
            return

        # Accept the connection after successful authentication
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for user {user_id}")
            
        # Add to manager
        await notification_manager.connect(websocket, user_id)
        
        try:
            while True:
                data = await websocket.receive_json()
                logger.info(f"Received message from user {user_id}: {data}")
                
                # Echo back the message for testing
                await notification_manager.broadcast_to_user(user_id, {
                    "type": "notification",
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                })
                
        except WebSocketDisconnect:
            notification_manager.disconnect(websocket, user_id)
            logger.info(f"WebSocket disconnected for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in WebSocket connection for user {user_id}: {str(e)}")
            await websocket.close(code=1011)  # Internal error
            
    except Exception as e:
        logger.error(f"Error establishing WebSocket connection: {str(e)}")
        try:
            await websocket.close(code=1011)  # Internal error
        except:
            pass 