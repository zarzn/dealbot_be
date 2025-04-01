#!/usr/bin/env python
"""Create initial data for the database.

This script creates initial data in the database for the AI Agentic Deals System.
It includes creating a default user account and other essential data.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
import json
import sys
import os
import random
import string
import hashlib
from typing import List, Dict, Any
import base64
import bcrypt

import asyncpg
import aiohttp
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_async_db_session, get_async_db_context
from core.services.auth import get_password_hash
from core.models.enums import (
    MarketType, MarketStatus, DealStatus, UserStatus, 
    TokenTransactionType, BalanceChangeType
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Define default user IDs
ADMIN_USER_ID = "00000000-0000-4000-a000-000000000001"
TEST_USER_ID = "c516ed76-59a7-4c33-bc43-bb74fbc89fb0"
TEST_USER_EMAIL = "test@test.com"

async def create_default_users():
    """Create default admin and test users if they don't exist."""
    logger.info("=== CREATING DEFAULT USERS ===")
    logger.info("Connecting to database...")
    
    try:
        async with get_async_db_context() as session:
            logger.info("Checking if system admin user exists...")
            # Check if admin user exists
            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE email = 'admin@example.com'")
            )
            count = result.scalar_one()
            
            if count == 0:
                logger.info("CREATING ADMIN USER: Creating system admin user...")
                # Create admin user
                await session.execute(
                    text("""
                    INSERT INTO users (
                        id, email, name, password, status, 
                        created_at, updated_at
                    ) VALUES (
                        :id, :email, :name, :password, 'active',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """),
                    {
                        "id": ADMIN_USER_ID,
                        "email": "admin@example.com",
                        "name": "System Admin",
                        "password": get_password_hash("adminPassword123!")
                    }
                )
                await session.commit()
                logger.info(f"System admin user created with ID: {ADMIN_USER_ID}")
            else:
                logger.info("System admin user already exists, skipping creation")
            
            # Check if test user exists
            logger.info("Checking if test user exists...")
            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE email = 'test@test.com'")
            )
            count = result.scalar_one()
            
            if count == 0:
                logger.info("CREATING TEST USER: Creating test user...")
                # Create test user 
                await session.execute(
                    text("""
                    INSERT INTO users (
                        id, email, name, password, status, 
                        created_at, updated_at
                    ) VALUES (
                        :id, :email, :name, :password, 'active',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """),
                    {
                        "id": TEST_USER_ID,
                        "email": "test@test.com",
                        "name": "Test User",
                        "password": get_password_hash("testPassword123!")
                    }
                )
                await session.commit()
                logger.info(f"Test user created with ID: {TEST_USER_ID}")
            else:
                logger.info("Test user already exists, skipping creation")
    except Exception as e:
        logger.error(f"Error creating default users: {str(e)}")
        raise

async def create_default_markets():
    """Create default markets."""
    logger.info("=== CREATING DEFAULT MARKETS ===")
    
    try:
        async with get_async_db_context() as session:
            # Check if markets already exist
            result = await session.execute(text("SELECT COUNT(*) FROM markets"))
            count = result.scalar_one()
            
            if count > 0:
                logger.info(f"Found {count} markets already exist, skipping creation")
                return
            
            # Create default markets
            for market_type in ['amazon', 'ebay', 'walmart', 'bestbuy', 'target']:
                await session.execute(
                    text("""
                    INSERT INTO markets (
                        id, name, type, description, status, config, 
                        created_at, updated_at
                    ) VALUES (
                        :id, :name, :type, :description, 'active', :config,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "name": market_type.capitalize(),
                        "type": market_type,
                        "description": f"{market_type.capitalize()} marketplace",
                        "config": json.dumps({'supported_categories': ['electronics', 'home', 'clothing', 'books']})
                    }
                )
            
            await session.commit()
            logger.info("Default markets created successfully")
    except Exception as e:
        logger.error(f"Error creating default markets: {str(e)}")
        raise

async def create_sample_deals():
    """Create sample deals."""
    logger.info("=== CREATING SAMPLE DEALS ===")
    
    try:
        async with get_async_db_context() as session:
            # Check if deals already exist
            result = await session.execute(text("SELECT COUNT(*) FROM deals"))
            count = result.scalar_one()
            
            if count > 0:
                logger.info(f"Found {count} deals already exist, skipping creation")
                return
            
            # Get market IDs - use 'type' column instead of 'market_type'
            market_result = await session.execute(
                text("SELECT id, type FROM markets LIMIT 5")
            )
            markets = market_result.fetchall()
            
            if not markets:
                logger.warning("No markets found, skipping sample deals creation")
                return
            
            market_dict = {market[1]: market[0] for market in markets}
            
            # Sample deals data
            deals_data = [
                {
                    "title": "Sony WH-1000XM4 Wireless Noise-Canceling Headphones",
                    "url": "https://www.amazon.com/product/sony-wh1000xm4",
                    "price": 279.99,
                    "original_price": 349.99,
                    "description": "Industry-leading noise canceling with Dual Noise Sensor technology",
                    "category": "electronics",
                    "market_type": "amazon",
                    "image_url": "https://example.com/images/sony-wh1000xm4.jpg",
                },
                {
                    "title": "Nintendo Switch OLED Model",
                    "url": "https://www.bestbuy.com/product/nintendo-switch-oled",
                    "price": 349.99,
                    "original_price": 359.99,
                    "description": "7-inch OLED screen, enhanced audio, and wide adjustable stand",
                    "category": "electronics",
                    "market_type": "bestbuy",
                    "image_url": "https://example.com/images/nintendo-switch-oled.jpg",
                },
                {
                    "title": "Keurig K-Elite Coffee Maker",
                    "url": "https://www.target.com/product/keurig-k-elite",
                    "price": 149.99,
                    "original_price": 189.99,
                    "description": "Single serve coffee maker with strong brew and iced coffee settings",
                    "category": "home",
                    "market_type": "target",
                    "image_url": "https://example.com/images/keurig-k-elite.jpg",
                },
                {
                    "title": "Apple iPad Air 10.9-inch (2022)",
                    "url": "https://www.walmart.com/product/apple-ipad-air",
                    "price": 559.00,
                    "original_price": 599.00,
                    "description": "10.9-inch Liquid Retina display with M1 chip",
                    "category": "electronics",
                    "market_type": "walmart",
                    "image_url": "https://example.com/images/ipad-air.jpg",
                },
                {
                    "title": "Samsung 55-inch Class QLED 4K Smart TV",
                    "url": "https://www.amazon.com/product/samsung-qled-tv",
                    "price": 799.99,
                    "original_price": 999.99,
                    "description": "4K QLED display with Quantum HDR and Alexa Built-in",
                    "category": "electronics",
                    "market_type": "amazon",
                    "image_url": "https://example.com/images/samsung-qled-tv.jpg",
                }
            ]
            
            # Create sample deals
            for deal_data in deals_data:
                market_id = market_dict.get(deal_data["market_type"])
                if not market_id:
                    continue
                
                deal_id = str(uuid.uuid4())
                
                # Insert deal
                await session.execute(
                    text("""
                    INSERT INTO deals (
                        id, title, url, price, original_price, description, category, 
                        market_id, image_url, status, user_id, created_at, updated_at
                    ) VALUES (
                        :id, :title, :url, :price, :original_price, :description, :category,
                        :market_id, :image_url, 'active', :user_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """),
                    {
                        "id": deal_id,
                        "title": deal_data["title"],
                        "url": deal_data["url"],
                        "price": deal_data["price"],
                        "original_price": deal_data["original_price"],
                        "description": deal_data["description"],
                        "category": deal_data["category"],
                        "market_id": market_id,
                        "image_url": deal_data["image_url"],
                        "user_id": TEST_USER_ID
                    }
                )
                
                # Create price points
                for days_ago in range(10, 0, -1):
                    price_variance = random.uniform(-0.10, 0.05)  # -10% to +5%
                    price = deal_data["price"] * (1 + price_variance)
                    
                    await session.execute(
                        text("""
                        INSERT INTO price_points (
                            deal_id, price, source, timestamp, created_at
                        ) VALUES (
                            :deal_id, :price, :source, :timestamp, CURRENT_TIMESTAMP
                        )
                        """),
                        {
                            "deal_id": deal_id,
                            "price": price,
                            "source": deal_data["market_type"],
                            "timestamp": datetime.now(timezone.utc) - timedelta(days=days_ago)
                        }
                    )
            
            await session.commit()
            logger.info("Sample deals created successfully")
    except Exception as e:
        logger.error(f"Error creating sample deals: {str(e)}")
        raise

async def create_test_goals():
    """Create test goals for test user."""
    logger.info("=== CREATING TEST GOALS ===")
    
    try:
        async with get_async_db_context() as session:
            # Check if test goals already exist
            existing_goals = await session.execute(
                text(f"SELECT COUNT(*) FROM goals WHERE user_id = '{TEST_USER_ID}'")
            )
            count = existing_goals.scalar()
            
            if count > 0:
                logger.info(f"Test goals already exist for user {TEST_USER_ID}, skipping...")
                return
            
            # Create test goals for the test user
            electronics_goal = await session.execute(
                text("""
                INSERT INTO goals (
                    id, user_id, item_category, title, description, constraints, 
                    deadline, status, priority, created_at, updated_at
                )
                VALUES (
                    gen_random_uuid(), 
                    :user_id, 
                    'electronics', 
                    'Gaming Laptop Under $1200', 
                    'Looking for a gaming laptop with at least 16GB RAM, 512GB SSD, and a powerful GPU',
                    '{"ram": "16GB", "storage": "512GB", "gpu": "RTX 3060 or better", "max_price": 1200.00, "target_price": 1000.00}',
                    (CURRENT_DATE + INTERVAL '30 days'),
                    'active',
                    'high',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                RETURNING id
                """),
                {"user_id": TEST_USER_ID}
            )
            
            clothing_goal = await session.execute(
                text("""
                INSERT INTO goals (
                    id, user_id, item_category, title, description, constraints, 
                    deadline, status, priority, created_at, updated_at
                )
                VALUES (
                    gen_random_uuid(), 
                    :user_id, 
                    'clothing', 
                    'Running Shoes for Marathon Training', 
                    'Need comfortable running shoes for marathon training with good cushioning and support',
                    '{"size": "US 10", "type": "Long-distance running", "features": ["Good cushioning", "Support"], "max_price": 160.00, "target_price": 120.00}',
                    (CURRENT_DATE + INTERVAL '14 days'),
                    'active',
                    'medium',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                RETURNING id
                """),
                {"user_id": TEST_USER_ID}
            )
            
            electronics_goal_id = electronics_goal.scalar()
            clothing_goal_id = clothing_goal.scalar()
            
            await session.commit()
            logger.info(f"Test goals created successfully for user {TEST_USER_ID}: " +
                      f"Electronics Goal ({electronics_goal_id}), Clothing Goal ({clothing_goal_id})")
    except Exception as e:
        logger.error(f"Error creating test goals: {str(e)}")
        raise

async def create_initial_tokens():
    """Create initial token transactions for test users."""
    logger.info("=== CREATING INITIAL TOKENS ===")
    
    try:
        async with get_async_db_context() as session:
            # Check if token transactions already exist
            existing_tokens = await session.execute(text("SELECT COUNT(*) FROM token_transactions"))
            count = existing_tokens.scalar()
            
            if count > 0:
                logger.info("Token transactions already exist, skipping...")
                return
            
            # Get test user ID
            result = await session.execute(
                text(f"SELECT id FROM users WHERE email = '{TEST_USER_EMAIL}'")
            )
            test_user = result.fetchone()
            
            if not test_user:
                logger.warning("Test user not found, skipping initial tokens creation")
                return
            
            user_id = test_user[0]
            
            # Add initial tokens to test user
            logger.info("Adding initial tokens to test user...")
            await session.execute(
                text("""
                    INSERT INTO token_transactions (
                        id, user_id, amount, meta_data, type, 
                        status, created_at
                    ) VALUES (
                        :id, :user_id, :amount, :meta_data, :type, 
                        :status, CURRENT_TIMESTAMP
                    )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "amount": 1000,
                        "meta_data": json.dumps({"description": "Initial tokens allocation"}),
                        "type": "credit",
                        "status": "completed"
                    }
                )
            
            # Add sample token transactions
            for i, (amount, trans_type, description) in enumerate([
                (50, "deduction", "AI analysis of deal: Sony WH-1000XM4"),
                (25, "deduction", "AI analysis of deal: iRobot Roomba"),
                (100, "credit", "Referral bonus"),
                (75, "deduction", "Market trend analysis"),
                (200, "credit", "Monthly subscription bonus")
            ]):
                await session.execute(
                    text("""
                    INSERT INTO token_transactions (
                        id, user_id, amount, meta_data, type, 
                        status, created_at
                    ) VALUES (
                        :id, :user_id, :amount, :meta_data, :type, 
                        :status, :created_at
                    )
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "amount": amount,
                        "meta_data": json.dumps({"description": description}),
                        "type": trans_type,
                        "status": "completed",
                        "created_at": datetime.utcnow() - timedelta(days=i+1)
                    }
                )
            
            await session.commit()
            logger.info("Initial tokens created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create initial tokens: {str(e)}")
        raise

async def run_initial_data_creation():
    """Run the initial data creation process."""
    logger.info("Opening database session for initial data creation...")
    try:
        async with get_async_db_context() as session:
            # Create users
            logger.info("Step 1/5: Creating default users...")
            await create_default_users()
            
            # Create markets
            logger.info("Step 2/5: Creating default markets...")
            await create_default_markets()
            
            # Create deals
            logger.info("Step 3/5: Creating sample deals...")
            await create_sample_deals()
            
            # Create test goals
            logger.info("Step 4/5: Creating test goals...")
            await create_test_goals()
            
            # Create initial tokens
            logger.info("Step 5/5: Creating initial tokens...")
            await create_initial_tokens()
                
            logger.info("Initial data creation completed successfully")
            return True
    except Exception as e:
        logger.error(f"INITIAL DATA ERROR: Failed to create initial data: {str(e)}")
        raise

def main():
    """Main function."""
    try:
        logger.info("Starting create_initial_data.py script...")
        success = asyncio.run(run_initial_data_creation())
        
        if success:
            logger.info("create_initial_data.py completed successfully!")
            sys.exit(0)
        else:
            logger.error("create_initial_data.py failed!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled exception in create_initial_data.py: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 