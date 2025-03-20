#!/usr/bin/env python
"""
This script verifies notification types across the system to ensure consistency.

It checks:
1. Database notification types actually used
2. The NotificationType enum definition
3. Reports on any inconsistencies
"""

import asyncio
import asyncpg
import logging
from collections import Counter

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection parameters
DB_HOST = "deals_postgres"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "12345678"
DB_NAME = "agentic_deals"

# Backend notification types from enum definition
BACKEND_TYPES = [
    "system", "deal", "goal", "price_alert", "token", "security", "market"
]

async def get_db_connection():
    """Get a database connection"""
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

async def check_db_notification_types(conn):
    """Check notification types in the database"""
    logger.info("Checking notification types in database...")
    
    # Check all distinct types in the notifications table
    query = "SELECT DISTINCT type FROM notifications ORDER BY type;"
    db_types = await conn.fetch(query)
    
    used_types = [row['type'] for row in db_types]
    logger.info(f"Types actually used in database: {', '.join(used_types)}")
    
    # Count usage of each type
    type_counts_query = """
    SELECT type, COUNT(*) as count 
    FROM notifications 
    GROUP BY type 
    ORDER BY count DESC;
    """
    type_counts = await conn.fetch(type_counts_query)
    
    logger.info("Notification type usage in database:")
    for row in type_counts:
        logger.info(f"  {row['type']}: {row['count']} notifications")
    
    # Check for types in database not in backend definition
    unknown_types = [t for t in used_types if t not in BACKEND_TYPES]
    if unknown_types:
        logger.warning(f"Found types in database not defined in backend enum: {', '.join(unknown_types)}")
    
    # Check for types in backend definition not used in database
    unused_types = [t for t in BACKEND_TYPES if t not in used_types]
    if unused_types:
        logger.info(f"Backend types not used in database: {', '.join(unused_types)}")
    
    return used_types, type_counts

async def check_enum_definition(conn):
    """Check the notification type enum definition in the database"""
    logger.info("Checking notification type enum definition in database...")
    
    # Query enum values
    query = """
    SELECT n.nspname AS enum_schema,
           t.typname AS enum_name,
           e.enumlabel AS enum_value
    FROM pg_type t
    JOIN pg_enum e ON t.oid = e.enumtypid
    JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typname = 'notificationtype'
    ORDER BY e.enumsortorder;
    """
    enum_values = await conn.fetch(query)
    
    if not enum_values:
        logger.warning("No NotificationType enum found in database!")
        return []
    
    db_enum_values = [row['enum_value'] for row in enum_values]
    logger.info(f"NotificationType enum values in database: {', '.join(db_enum_values)}")
    
    # Check for values in backend definition not in database enum
    missing_values = [t for t in BACKEND_TYPES if t not in db_enum_values]
    if missing_values:
        logger.warning(f"Backend types missing from database enum: {', '.join(missing_values)}")
    
    # Check for values in database enum not in backend definition
    extra_values = [t for t in db_enum_values if t not in BACKEND_TYPES]
    if extra_values:
        logger.warning(f"Database enum values not in backend definition: {', '.join(extra_values)}")
    
    return db_enum_values

async def check_recent_notifications(conn):
    """Check the most recent notifications in the database"""
    logger.info("Checking recent notifications in the database...")
    
    query = """
    SELECT id, user_id, title, message, type, created_at 
    FROM notifications 
    ORDER BY created_at DESC 
    LIMIT 5;
    """
    recent = await conn.fetch(query)
    
    if not recent:
        logger.info("No notifications found in database")
        return
    
    logger.info(f"Found {len(recent)} recent notifications:")
    for idx, notif in enumerate(recent, 1):
        logger.info(f"  Notification {idx}:")
        logger.info(f"    ID: {notif['id']}")
        logger.info(f"    Title: {notif['title']}")
        logger.info(f"    Type: {notif['type']}")
        logger.info(f"    Created: {notif['created_at']}")

async def main():
    """Main function"""
    logger.info("Starting notification type verification")
    conn = None
    try:
        conn = await get_db_connection()
        
        # Check database notification types
        used_types, type_counts = await check_db_notification_types(conn)
        
        # Check enum definition
        db_enum_values = await check_enum_definition(conn)
        
        # Check recent notifications
        await check_recent_notifications(conn)
        
        # Overall status report
        logger.info("\nNotification Type Verification Summary:")
        
        # Type definitions match
        if set(BACKEND_TYPES) == set(db_enum_values):
            logger.info("✅ Backend type definitions match database enum")
        else:
            logger.warning("❌ Backend type definitions DO NOT match database enum")
        
        # All used types are in backend definition
        unknown_types = [t for t in used_types if t not in BACKEND_TYPES]
        if not unknown_types:
            logger.info("✅ All notification types in database are defined in backend")
        else:
            logger.warning(f"❌ Found {len(unknown_types)} types in database not defined in backend")
        
        # Summary of used types
        type_usage = {row['type']: row['count'] for row in type_counts}
        logger.info(f"Most used type: {max(type_usage.items(), key=lambda x: x[1])[0]}")
        
        logger.info("Notification type verification completed")
    except Exception as e:
        logger.error(f"Error in verification process: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    asyncio.run(main()) 