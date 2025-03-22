"""Direct test for shared content functionality.

This script tests the sharing functionality by directly interacting with
the database and services, bypassing HTTP requests.
"""

import asyncio
import uuid
import logging
import random
import string
import json
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder

from core.database import get_async_db_session, async_engine, AsyncSessionLocal
from core.models.shared_content import (
    SharedContent, 
    ShareContentRequest,
    ShareableContentType,
    ShareVisibility
)
from core.models.user import User
from core.services.sharing import SharingService
from core.utils.json_utils import sanitize_for_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_test_user_id() -> uuid.UUID:
    """Get a test user ID from the database."""
    async with AsyncSessionLocal() as db:
        try:
            # Find any user in the database
            from sqlalchemy import select
            stmt = select(User).limit(1)
            result = await db.execute(stmt)
            user = result.scalars().first()
            
            if user:
                logger.info(f"Found test user: {user.id}")
                return user.id
            else:
                # If no user exists, create a test user
                logger.info("No users found, creating test user")
                test_user = User(
                    email="test@example.com",
                    is_active=True,
                    is_superuser=False,
                    firstname="Test",
                    lastname="User"
                )
                db.add(test_user)
                await db.commit()
                await db.refresh(test_user)
                logger.info(f"Created test user: {test_user.id}")
                return test_user.id
        except Exception as e:
            logger.error(f"Error getting test user: {str(e)}")
            # Generate a random UUID as fallback
            random_id = uuid.uuid4()
            logger.info(f"Using random UUID as user ID: {random_id}")
            return random_id

async def get_test_deal_id() -> uuid.UUID:
    """Get a test deal ID from the database."""
    async with AsyncSessionLocal() as db:
        try:
            # Find any deal in the database
            from sqlalchemy import select
            from core.models.deal import Deal
            stmt = select(Deal).limit(1)
            result = await db.execute(stmt)
            deal = result.scalars().first()
            
            if deal:
                logger.info(f"Found test deal: {deal.id}")
                return deal.id
            else:
                logger.info("No deals found")
                # Generate a random UUID as fallback
                random_id = uuid.uuid4()
                logger.info(f"Using random UUID as deal ID: {random_id}")
                return random_id
        except Exception as e:
            logger.error(f"Error getting test deal: {str(e)}")
            # Generate a random UUID as fallback
            random_id = uuid.uuid4()
            logger.info(f"Using random UUID as deal ID: {random_id}")
            return random_id

async def test_create_shareable_content():
    """Test creation of a shareable content item."""
    async with AsyncSessionLocal() as db:
        try:
            print("\n===== Testing Creation of Shareable Content =====")
            
            # Get a test user ID
            user_id = await get_test_user_id()
            print(f"Using user ID: {user_id}")
            
            # Get a test deal ID
            deal_id = await get_test_deal_id()
            print(f"Using deal ID: {deal_id}")
            
            # Create a share request
            share_request = ShareContentRequest(
                content_type=ShareableContentType.DEAL,
                content_id=str(deal_id),
                title=f"Test Share {random.randint(1000, 9999)}",
                description="Testing the share functionality directly",
                visibility=ShareVisibility.PUBLIC,
                expiration_days=30,
                include_personal_notes=False
            )
            
            # Create the shareable content
            sharing_service = SharingService(db)
            base_url = "http://localhost:8000"  # This is just for generating the URL
            
            result = await sharing_service.create_shareable_content(
                user_id=user_id,
                share_request=share_request,
                base_url=base_url
            )
            
            # Check the result
            print(f"✅ Share created successfully")
            print(f"Share ID: {result.share_id}")
            print(f"Title: {result.title}")
            print(f"Shareable link: {result.shareable_link}")
            
            return result.share_id
            
        except Exception as e:
            print(f"❌ Error creating shareable content: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

async def test_get_shareable_content(share_id: str):
    """Test retrieval of a shareable content item."""
    async with AsyncSessionLocal() as db:
        try:
            print("\n===== Testing Retrieval of Shareable Content =====")
            print(f"Retrieving share with ID: {share_id}")
            
            # Get the shared content
            sharing_service = SharingService(db)
            
            result = await sharing_service.get_shared_content(
                share_id=share_id,
                viewer_id=None,  # Anonymous viewer
                viewer_ip="127.0.0.1",
                viewer_device="Direct test script",
                referrer=None
            )
            
            # Check the result
            print(f"✅ Share retrieved successfully")
            print(f"Title: {result.title}")
            print(f"Content type: {result.content_type}")
            print(f"View count: {result.view_count}")
            
            # Get the sanitized JSON for verification
            sanitized_result = sanitize_for_json(result.model_dump())
            print(f"Content: {json.dumps(sanitized_result, indent=2)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error getting shareable content: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

async def run_tests():
    """Run all tests."""
    # Test creating a shareable content item
    share_id = await test_create_shareable_content()
    
    if share_id:
        # Test retrieving the shareable content
        await test_get_shareable_content(share_id)
    else:
        print("❌ Cannot run retrieval test without a valid share ID")

if __name__ == "__main__":
    asyncio.run(run_tests()) 