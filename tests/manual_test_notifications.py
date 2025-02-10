"""Manual test script for notification endpoints."""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from uuid import uuid4

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "testpassword123"

async def login() -> str:
    """Login and get access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
        )
        data = response.json()
        return data["access_token"]

async def test_notification_flow():
    """Test the complete notification flow."""
    try:
        # Login
        token = await login()
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient() as client:
            # 1. Create a notification
            print("\n1. Creating notification...")
            create_response = await client.post(
                f"{BASE_URL}/notifications",
                headers=headers,
                json={
                    "title": "Test Notification",
                    "message": "This is a test notification",
                    "type": "system",
                    "channels": ["in_app"],
                    "priority": "medium",
                    "data": {"test_key": "test_value"}
                }
            )
            print(f"Create Response: {create_response.status_code}")
            print(json.dumps(create_response.json(), indent=2))
            
            notification_id = create_response.json()["id"]

            # 2. Get notifications
            print("\n2. Getting notifications...")
            get_response = await client.get(
                f"{BASE_URL}/notifications",
                headers=headers
            )
            print(f"Get Response: {get_response.status_code}")
            print(json.dumps(get_response.json(), indent=2))

            # 3. Get unread count
            print("\n3. Getting unread count...")
            count_response = await client.get(
                f"{BASE_URL}/notifications/unread/count",
                headers=headers
            )
            print(f"Unread Count Response: {count_response.status_code}")
            print(f"Unread Count: {count_response.json()}")

            # 4. Mark notification as read
            print("\n4. Marking notification as read...")
            mark_read_response = await client.put(
                f"{BASE_URL}/notifications/{notification_id}/read",
                headers=headers
            )
            print(f"Mark Read Response: {mark_read_response.status_code}")
            print(json.dumps(mark_read_response.json(), indent=2))

            # 5. Get notification preferences
            print("\n5. Getting notification preferences...")
            prefs_response = await client.get(
                f"{BASE_URL}/notifications/preferences",
                headers=headers
            )
            print(f"Preferences Response: {prefs_response.status_code}")
            print(json.dumps(prefs_response.json(), indent=2))

            # 6. Update notification preferences
            print("\n6. Updating notification preferences...")
            update_prefs_response = await client.put(
                f"{BASE_URL}/notifications/preferences",
                headers=headers,
                json={
                    "enabled_channels": ["email", "in_app"],
                    "email_digest": True,
                    "push_enabled": False,
                    "do_not_disturb": False
                }
            )
            print(f"Update Preferences Response: {update_prefs_response.status_code}")
            print(json.dumps(update_prefs_response.json(), indent=2))

            # 7. Delete notification
            print("\n7. Deleting notification...")
            delete_response = await client.delete(
                f"{BASE_URL}/notifications",
                headers=headers,
                json={"notification_ids": [notification_id]}
            )
            print(f"Delete Response: {delete_response.status_code}")
            print(json.dumps(delete_response.json(), indent=2))

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_notification_flow()) 