"""Manual test script for WebSocket notifications."""

import asyncio
import json
import uuid
import httpx
from datetime import datetime
from typing import Dict, Any
import logging
from websockets.client import connect as ws_connect

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/api/v1/notifications/ws"

# Test user credentials
TEST_USER_EMAIL = "gluked@gmail.com"
TEST_USER_PASSWORD = "12345678"

async def get_auth_token():
    """Get authentication token for test user."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                data={
                    "username": TEST_USER_EMAIL,  # OAuth2 uses username field
                    "password": TEST_USER_PASSWORD,
                    "grant_type": "password"
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Auth response: {data}")  # Log the response for debugging
            return data["access_token"]
    except Exception as e:
        logger.error(f"Failed to get auth token: {e}")
        if isinstance(e, httpx.HTTPStatusError):
            logger.error(f"Response content: {e.response.content}")  # Log response content for debugging
        raise

async def send_test_notification(token: str):
    """Send test notification through WebSocket."""
    try:
        ws_url = f"{WS_URL}?token={token}"
        logger.info(f"Connecting to WebSocket at {ws_url}")
        
        async with ws_connect(ws_url) as websocket:
            logger.info("WebSocket connection established")
            
            # Send test message
            test_message = {"type": "test", "content": "Test notification"}
            await websocket.send(json.dumps(test_message))
            logger.info(f"Sent test message: {test_message}")
            
            # Wait for response
            response = await websocket.recv()
            logger.info(f"Received response: {response}")
            
            # Keep connection open for a bit to receive any notifications
            await asyncio.sleep(5)
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        raise

async def run_notification_tests():
    """Run WebSocket notification tests."""
    try:
        # Get auth token
        token = await get_auth_token()
        logger.info("Successfully obtained auth token")
        
        # Test notifications
        await send_test_notification(token)
        logger.info("Notification test completed successfully")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_notification_tests()) 