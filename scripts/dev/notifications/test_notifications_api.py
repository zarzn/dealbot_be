#!/usr/bin/env python
"""
Test script to verify the notifications API endpoints from within the Docker container
"""
import json
import asyncio
import logging
import sys
from typing import Dict, Any, Optional

import httpx
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("test_notifications_api")

# Constants
API_BASE_URL = "http://localhost:8000/api/v1"  # When running inside container, this should work
TEST_USER_EMAIL = "test@test.com"
TEST_USER_PASSWORD = "test"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str


async def login(client: httpx.AsyncClient) -> Optional[str]:
    """Login with test user credentials and return the JWT token"""
    try:
        # Use form data instead of JSON for OAuth2PasswordRequestForm
        response = await client.post(
            f"{API_BASE_URL}/auth/login",
            data={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        response.raise_for_status()
        login_data = response.json()
        logger.info(f"Login successful: {login_data}")
        
        # Validate and parse the login response
        login_response = LoginResponse(**login_data)
        return login_response.access_token
    except httpx.HTTPStatusError as e:
        logger.error(f"Login failed with status {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return None


async def get_notifications(client: httpx.AsyncClient, token: str) -> Optional[Dict[str, Any]]:
    """Get notifications for the authenticated user"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(
            f"{API_BASE_URL}/notifications",
            headers=headers,
            params={"page": 1, "limit": 20}
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Got notifications: {json.dumps(data, indent=2)}")
        return data
    except httpx.HTTPStatusError as e:
        logger.error(f"Get notifications failed with status {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Get notifications error: {str(e)}")
        return None


async def mark_notification_as_read(client: httpx.AsyncClient, token: str, notification_id: str) -> bool:
    """Mark a notification as read"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.put(
            f"{API_BASE_URL}/notifications/{notification_id}/read",
            headers=headers
        )
        response.raise_for_status()
        logger.info(f"Marked notification {notification_id} as read")
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Mark as read failed with status {e.response.status_code}: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Mark as read error: {str(e)}")
        return False


async def main():
    """Main test function"""
    logger.info("Starting notifications API test")
    
    # timeout for slow responses
    timeout = httpx.Timeout(30.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Step 1: Login to get JWT token
        token = await login(client)
        if not token:
            logger.error("Failed to login. Exiting.")
            return
        
        # Step 2: Get notifications
        notifications_data = await get_notifications(client, token)
        if not notifications_data:
            logger.error("Failed to get notifications. Exiting.")
            return
        
        # Log the type of the response for debugging
        logger.info(f"Notifications response type: {type(notifications_data)}")
        
        # Check if the response is an array or an object with a notifications field
        if isinstance(notifications_data, list):
            notifications = notifications_data
            logger.info(f"Response is an array with {len(notifications)} notifications")
        else:
            # If it's an object with a notifications field
            notifications = notifications_data.get("notifications", [])
            logger.info(f"Response is an object with {len(notifications)} notifications")
        
        # Step 3: If there are notifications, mark the first one as read
        if notifications:
            notification_id = notifications[0].get("id")
            if notification_id:
                success = await mark_notification_as_read(client, token, notification_id)
                if success:
                    logger.info(f"Successfully marked notification {notification_id} as read")
                else:
                    logger.error(f"Failed to mark notification {notification_id} as read")
        else:
            logger.warning("No notifications found to mark as read")

if __name__ == "__main__":
    asyncio.run(main()) 