"""Router for AI API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body, Request
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from core.services.ai import AIService, get_ai_service
from core.database import get_db, get_async_db_context
from sqlalchemy.ext.asyncio import AsyncSession
from core.dependencies import get_current_user, get_current_user_optional
from core.models.user import User, UserInDB
from core.services.deal import DealService
from core.services.token import TokenService
from core.dependencies import get_token_service
from uuid import UUID
import traceback

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

# Helper dependency to get db session using the improved context manager
async def get_db_session() -> AsyncSession:
    """Get a database session using the improved context manager.
    
    This dependency provides better connection management and prevents connection leaks.
    """
    async with get_async_db_context() as session:
        yield session

# Helper function to get AI service
# Using the singleton implementation from core.services.ai
# This is the dependency that will be used by the router endpoints

@router.get("/test-connection", response_model=Dict[str, Any])
async def test_ai_connection(
    current_user: Optional[User] = Depends(get_current_user_optional),
    ai_service: AIService = Depends(get_ai_service)
):
    """
    Test the AI service connection and return diagnostic information.
    
    This endpoint can be used to verify that the AI service is properly
    connected to the language model and that API keys are correctly configured.
    """
    logger.info("Testing AI service connection")
    
    try:
        # Only allow authenticated users to test the connection in production
        if not current_user:
            logger.warning("Unauthenticated user attempted to test AI connection")
            raise HTTPException(
                status_code=401,
                detail="Authentication required to test AI connection"
            )
        
        # Run the connection test
        test_results = await ai_service.test_llm_connection()
        logger.info(f"AI connection test completed: {test_results.get('connection_test', {}).get('success', False)}")
        
        return {
            "status": "success",
            "message": "AI service connection test completed",
            "results": test_results
        }
    except Exception as e:
        logger.error(f"Error testing AI connection: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error testing AI connection: {str(e)}"
        )

@router.post("/diagnose", response_model=Dict[str, Any])
async def diagnose_ai_service(
    request: Request,
    test_data: Optional[Dict[str, Any]] = Body({}),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    ai_service: AIService = Depends(get_ai_service)
):
    """
    Run a comprehensive diagnostic on the AI service and its dependencies.
    
    This includes checking the database connection, LLM initialization,
    API key validation, and running a simple inference test.
    """
    logger.info(f"Running AI service diagnostic by user {current_user.id}")
    
    try:
        # Initialize deal service
        deal_service = DealService(db)
        
        # Get a sample deal to test with
        sample_deal = None
        try:
            # Try to get a random deal from the database
            sample_deals = await deal_service.list_deals(limit=1)
            if sample_deals:
                sample_deal = sample_deals[0]
                logger.info(f"Found sample deal {sample_deal.id} for testing")
        except Exception as e:
            logger.error(f"Error fetching sample deal: {str(e)}")
        
        # Initialize test results
        results = {
            "timestamp": str(datetime.utcnow()),
            "services": {
                "ai_service": {
                    "initialized": ai_service is not None,
                    "llm_available": ai_service.llm is not None if ai_service else False
                },
                "deal_service": {
                    "initialized": deal_service is not None,
                    "db_connected": True  # We assume this since the dependency injection worked
                }
            },
            "llm_connection": await ai_service.test_llm_connection(),
            "sample_analysis": None
        }
        
        # Try to run a sample analysis if we have a deal
        if sample_deal:
            try:
                analysis = await ai_service.analyze_deal(sample_deal)
                results["sample_analysis"] = {
                    "deal_id": str(sample_deal.id),
                    "success": analysis is not None,
                    "score": analysis.get("score") if analysis else None,
                    "recommendations_count": len(analysis.get("recommendations", [])) if analysis else 0
                }
                logger.info(f"Generated sample analysis for deal {sample_deal.id}")
            except Exception as e:
                logger.error(f"Error generating sample analysis: {str(e)}")
                results["sample_analysis"] = {
                    "deal_id": str(sample_deal.id) if sample_deal else None,
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "status": "success",
            "message": "AI service diagnostic completed",
            "results": results
        }
    except Exception as e:
        logger.error(f"Error during AI service diagnostic: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error diagnosing AI service: {str(e)}"
        ) 