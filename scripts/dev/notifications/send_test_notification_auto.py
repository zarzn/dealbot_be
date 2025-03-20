"""
Test Notification Script for WebSocket (Automated Version)
Run this inside the Docker container to test notification functionality without user input
"""

import asyncio
import websockets.client
import logging
import json
import uuid
from datetime import datetime, timedelta
import random
import traceback
import asyncpg
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define notification types
NOTIFICATION_TYPES = [
    "deal",
    "goal",
    "system",
    "market"
]

# Mapping from frontend types to backend types
TYPE_MAPPING = {
    "deal": "info",
    "goal": "success",
    "system": "warning",
    "market": "info"
}

# Define notification content templates
NOTIFICATION_CONTENT = {
    "deal": {
        "titles": [
            "New Deal Found",
            "Deal Alert: Special Offer",
            "We Found a Deal You Might Like"
        ],
        "messages": [
            "We found a deal matching your criteria for '{product}'",
            "Your goal for '{product}' has a new matching deal",
            "Check out this deal for '{product}' we found for you"
        ]
    },
    "goal": {
        "titles": [
            "Goal Completed",
            "Achievement Unlocked",
            "Goal Target Reached"
        ],
        "messages": [
            "Your goal for '{product}' has been marked as completed",
            "Congratulations! You've reached your goal for '{product}'",
            "Goal completed: Your target for '{product}' has been achieved"
        ]
    },
    "market": {
        "titles": [
            "Price Drop Alert",
            "Price Changed on Tracked Item",
            "Price Update Notification"
        ],
        "messages": [
            "The price of '{product}' has dropped from ${old_price} to ${new_price}",
            "Good news! '{product}' is now ${new_price} (was ${old_price})",
            "Price alert: '{product}' is now available for ${new_price}"
        ]
    },
    "system": {
        "titles": [
            "System Notification",
            "Important Information",
            "Agentic Deals Update"
        ],
        "messages": [
            "Your account has been successfully updated",
            "New feature alert: We've added new capabilities to your account",
            "Maintenance complete: All systems are functioning normally"
        ]
    }
}

# Sample products
SAMPLE_PRODUCTS = [
    "iPhone 15 Pro",
    "Samsung Galaxy S24",
    "MacBook Air M3",
    "Dell XPS 13",
    "Sony PlayStation 5",
    "Xbox Series X",
    "Nintendo Switch OLED",
    "AirPods Pro 2",
    "Samsung 65\" 4K Smart TV",
    "Dyson V12 Vacuum",
    "Bose QuietComfort Earbuds",
    "GoPro Hero 11",
    "Amazon Kindle Paperwhite",
    "Canon EOS R7",
    "LG OLED C2 TV"
]

async def get_db_connection():
    """Get a connection to the PostgreSQL database."""
    # Try different host configurations
    hosts_to_try = ["deals_postgres", "localhost", "database", "127.0.0.1"]
    
    for host in hosts_to_try:
        try:
            logger.info(f"Trying to connect to database at {host}...")
            conn = await asyncpg.connect(
                host=host,
                port=5432,
                user="postgres",
                password="12345678",
                database="agentic_deals"
            )
            logger.info(f"Successfully connected to database at {host}")
            return conn
        except Exception as e:
            logger.warning(f"Failed to connect to database at {host}: {str(e)}")
    
    logger.error("All database connection attempts failed")
    return None
        
async def store_notification_in_db(notification_data):
    """Store notification in database using direct connection"""
    conn = await get_db_connection()
    if not conn:
        logger.error("Cannot store notification: no database connection")
        return False
        
    try:
        # Extract notification type from meta or type field
        notification_type = notification_data.get("type", "system")
        # Map frontend type to backend type if needed
        backend_type = notification_data.get("meta", {}).get("notification_type", notification_type)
        
        # Make sure we're using valid enum values
        if backend_type not in NOTIFICATION_TYPES:
            logger.warning(f"Invalid notification type: {backend_type}, falling back to 'system'")
            backend_type = "system"
            
        # Debug database structure 
        logger.info("--- Database debugging information ---")
        try:
            # List all tables to confirm notifications table exists
            tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            table_names = [t['table_name'] for t in tables]
            logger.info(f"Available tables in the database: {table_names}")
            
            # Find potential notification tables
            notification_tables = [t for t in table_names if 'notif' in t]
            logger.info(f"Potential notification tables: {notification_tables}")
            
            # Use the notifications table
            if 'notifications' in table_names:
                logger.info("Using table 'notifications' to store notification")
                
                # Check schema to ensure we have the right columns
                columns = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'notifications'
                """)
                column_names = [c['column_name'] for c in columns]
                logger.info(f"Columns in notifications table: {column_names}")
            else:
                logger.error("Could not find notifications table")
                return False
        except Exception as e:
            logger.error(f"Error inspecting database schema: {str(e)}")
            
        # Prepare data for insertion
        notification_id = notification_data.get("id", str(uuid.uuid4()))
        user_id = notification_data.get("user_id")
        title = notification_data.get("title", "Notification")
        message = notification_data.get("message", "")
        
        # Use valid enum values for notification type
        notification_type = backend_type
        
        # Prepare additional data
        created_at = datetime.now()
        priority = "medium"
        status = "delivered"
        channels = ["in_app"]
        
        # Create meta object
        meta = notification_data.get("meta", {})
        if not meta:
            meta = {}
            
        # Add deal or goal ID if present
        if "deal_id" in notification_data:
            meta["deal_id"] = notification_data["deal_id"]
        if "goal_id" in notification_data:
            meta["goal_id"] = notification_data["goal_id"]
        if "product" in notification_data:
            meta["product"] = notification_data["product"]
        if "notification_type" not in meta:
            meta["notification_type"] = notification_type
                    
        # Build query with parameters
        columns = ["id", "user_id", "title", "message", "type", "priority", "status", "channels", "created_at", "notification_metadata"]
        params = [f"${i+1}" for i in range(len(columns))]
        values = [notification_id, user_id, title, message, notification_type, priority, status, json.dumps(channels), created_at, json.dumps(meta)]
        
        query = f"""
        INSERT INTO notifications
        ({', '.join(columns)})
        VALUES ({', '.join(params)})
        RETURNING id
        """
        
        logger.info(f"Executing query: {query}")
        logger.info(f"With values: {values}")
        
        # Execute query
        result = await conn.fetchval(query, *values)
        
        logger.info(f"Successfully stored notification in database with ID: {result}")
        return True
    except Exception as e:
        logger.error(f"Failed to store notification in database: {str(e)}")
        return False
    finally:
        if conn:
            await conn.close()

async def get_test_user_id():
    """Get the test user's ID from the database."""
    conn = await get_db_connection()
    if not conn:
        logger.error("Cannot get test user ID: no database connection")
        return None
        
    try:
        # Query for the test user by email
        query = "SELECT id FROM users WHERE email = 'test@test.com'"
        result = await conn.fetchval(query)
        
        if result:
            logger.info(f"Found test user with ID: {result}")
            return str(result)
        else:
            logger.warning("Test user not found in database, falling back to system admin ID")
            return "00000000-0000-4000-a000-000000000001"  # Fallback to system admin
    except Exception as e:
        logger.error(f"Error getting test user ID: {str(e)}")
        return None
    finally:
        await conn.close()

async def send_notification(websocket, notification_type=None, user_id=None):
    """Send a random or specific type of notification"""
    # Choose a random type if not specified
    if not notification_type:
        notification_type = random.choice(NOTIFICATION_TYPES)
    
    # Get content templates for this type
    content = NOTIFICATION_CONTENT.get(notification_type, NOTIFICATION_CONTENT["system"])
    
    # Choose random content
    title = random.choice(content["titles"])
    message_template = random.choice(content["messages"])
    
    # Map backend notification type to frontend type
    frontend_type = TYPE_MAPPING.get(notification_type, "info")
    
    # Generate a unique ID for this notification
    notification_id = str(uuid.uuid4())
    
    # If no user ID was passed, use the default system admin user ID
    if not user_id:
        user_id = "00000000-0000-4000-a000-000000000001"  # Default to system admin user ID
    
    # Sample products to use in notifications
    sample_products = [
        {"name": "Samsung 65\" 4K Smart TV", "old_price": "899.99", "new_price": "699.99"},
        {"name": "Apple MacBook Pro", "old_price": "1299.99", "new_price": "1199.99"},
        {"name": "Sony Noise Cancelling Headphones", "old_price": "349.99", "new_price": "279.99"},
        {"name": "Dell XPS 13", "old_price": "1199.99", "new_price": "999.99"},
        {"name": "Nintendo Switch", "old_price": "299.99", "new_price": "249.99"}
    ]
    
    # Choose a random product
    product = random.choice(sample_products)
    
    # Format message with product details
    message = message_template.format(
        product=product["name"], 
        old_price=product["old_price"], 
        new_price=product["new_price"]
    )
    
    # Generate notification data with frontend-compatible format
    notification_data = {
        "id": notification_id,
        "user_id": user_id,  # Use the user ID that was passed in
        "title": title,
        "message": message,
        "type": frontend_type,  # Frontend-compatible type
        "read": False,
        "created_at": datetime.now().isoformat(),  # Use created_at instead of timestamp
        "meta": {
            "notification_type": notification_type
        }
    }
    
    # Add type-specific fields
    if notification_type == "deal":
        notification_data["deal_id"] = str(uuid.uuid4())
        notification_data["meta"]["goal_id"] = str(uuid.uuid4())
        notification_data["meta"]["product"] = product["name"]
    elif notification_type == "market":
        notification_data["deal_id"] = str(uuid.uuid4())
        notification_data["meta"]["old_price"] = product["old_price"]
        notification_data["meta"]["new_price"] = product["new_price"]
        notification_data["meta"]["product"] = product["name"]
    elif notification_type == "goal":
        notification_data["meta"]["goal_id"] = str(uuid.uuid4())
        notification_data["meta"]["product"] = product["name"]
    
    # Format websocket notification data
    websocket_data = {
        "type": "notification",
        "notification": notification_data
    }
    
    # Send notification through WebSocket
    logger.info(f"Sending notification: {websocket_data}")
    await websocket.send(json.dumps(websocket_data))
    
    # Also store in database directly
    logger.info("Also storing notification directly in database")
    db_stored = await store_notification_in_db(notification_data)
    
    if db_stored:
        logger.info("Notification successfully stored in database")
    else:
        logger.warning("Failed to store notification in database")
    
    # Wait for the response
    try:
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        logger.info(f"Received response: {json.loads(response)}")
    except asyncio.TimeoutError:
        logger.warning("Timed out waiting for response")
    except Exception as e:
        logger.error(f"Error receiving response: {str(e)}")

async def test_notifications_auto():
    """Connect to the WebSocket server and send test notifications automatically"""
    # First get the test user ID
    test_user_id = await get_test_user_id()
    if not test_user_id:
        logger.error("Could not determine test user ID, cannot proceed")
        return
        
    logger.info(f"Using test user ID: {test_user_id}")
    
    token = "test_websocket_token_test"  # Use test token
    uri = f"ws://localhost:8000/api/v1/notifications/ws?token={token}"
    
    logger.info(f"Connecting to WebSocket at {uri}")
    try:
        async with websockets.client.connect(uri) as websocket:
            logger.info("Connected to WebSocket server!")
            
            # Wait for welcome message
            welcome_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            welcome_data = json.loads(welcome_message)
            logger.info(f"Received welcome message: {welcome_data}")
            
            if welcome_data.get("type") == "connection_established":
                logger.info(f"Successfully authenticated as user: {welcome_data.get('user_id')}")
                
                # Send a ping message first
                logger.info("Sending ping message...")
                ping_message = {
                    "type": "ping",
                    "client": "test_script",
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(ping_message))
                
                # Wait for pong response
                pong_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                pong_data = json.loads(pong_message)
                logger.info(f"Received pong response: {pong_data}")
                
                # Automatically select notification configurations
                num_notifications = 3  # Send 3 notifications by default
                notification_types = ["deal", "goal", "system", "market"]  # Send one of each type
                
                # Send notifications
                logger.info(f"Sending {len(notification_types)} notification(s)...")
                for i, notification_type in enumerate(notification_types):
                    if i >= num_notifications:
                        break
                        
                    logger.info(f"Sending notification {i+1}/{num_notifications} of type: {notification_type}")
                    # Pass the test user ID to the send_notification function
                    await send_notification(websocket, notification_type, test_user_id)
                    if i < num_notifications - 1:  # Don't sleep after the last notification
                        await asyncio.sleep(1)  # Wait a bit between notifications
                
                logger.info("All notifications sent successfully!")
                
            else:
                logger.warning(f"Unexpected welcome message type: {welcome_data.get('type')}")
                
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    print("\n=== Automated WebSocket Notification Test Script ===\n")
    print("This script will connect to the WebSocket server and send test notifications automatically.\n")
    try:
        asyncio.run(test_notifications_auto())
    except KeyboardInterrupt:
        print("\nTest script interrupted by user.")
    except Exception as e:
        print(f"\nError running test script: {str(e)}")
    finally:
        print("\nTest script completed.") 