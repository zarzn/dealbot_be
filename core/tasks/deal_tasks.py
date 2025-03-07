"""
Deal-related background tasks.

This module contains background tasks for processing deals, including:
- Analyzing deals with AI
- Updating deal scores
- Processing deal batches
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from core.database import get_session
from core.models.deal import Deal
from core.services.ai import AIService
from core.services.deal import DealService
from core.repositories.deal import DealRepository
from core.services.redis import get_redis_service
from core.utils.metrics import track_metric, track_time

logger = logging.getLogger(__name__)

async def schedule_batch_deal_analysis(
    deal_ids: List[str],
    user_id: Optional[UUID] = None,
    priority: str = "normal"
) -> str:
    """
    Schedule background task for batch analysis of deals.
    
    Args:
        deal_ids: List of deal IDs to analyze
        user_id: Optional user ID requesting the analysis
        priority: Task priority (low, normal, high)
        
    Returns:
        Task ID for tracking
    """
    try:
        # Generate a task ID
        task_id = f"deal_analysis_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{len(deal_ids)}"
        
        # Get Redis service for task management
        try:
            redis = await get_redis_service()
            
            # Create task data
            task_data = {
                "task_id": task_id,
                "deal_ids": deal_ids,
                "user_id": str(user_id) if user_id else None,
                "priority": priority,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "total_deals": len(deal_ids),
                "completed_deals": 0
            }
            
            # Store task in Redis
            await redis.set(
                f"task:deal_analysis:{task_id}", 
                json.dumps(task_data),
                expire=86400  # 24 hours
            )
            
            # Add to processing queue with appropriate priority
            queue_key = f"queue:deal_analysis:{priority}"
            await redis.rpush(queue_key, task_id)
            
            # Increment counter for scheduled tasks
            track_metric("scheduled_deal_analysis_tasks")
        except Exception as e:
            logger.warning(f"Redis error during task scheduling: {str(e)}")
            # Continue execution even if Redis fails - the task can still be processed
        
        # Start processing task asynchronously
        asyncio.create_task(process_deal_analysis_task(task_id))
        
        return task_id
        
    except Exception as e:
        logger.error(f"Error scheduling batch deal analysis: {str(e)}")
        return f"error:{str(e)}"

async def process_deal_analysis_task(task_id: str) -> bool:
    """
    Process a deal analysis task.
    
    Args:
        task_id: Task ID to process
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Start timing
        start_time = datetime.utcnow()
        
        # Get Redis service
        redis = await get_redis_service()
        
        # Get task data
        task_data_str = await redis.get(f"task:deal_analysis:{task_id}")
        if not task_data_str:
            logger.error(f"Task {task_id} not found")
            return False
            
        task_data = json.loads(task_data_str)
        
        # Update status to processing
        task_data["status"] = "processing"
        task_data["started_at"] = datetime.utcnow().isoformat()
        await redis.set(
            f"task:deal_analysis:{task_id}", 
            json.dumps(task_data),
            expire=86400  # 24 hours
        )
        
        # Get deal IDs to process
        deal_ids = task_data.get("deal_ids", [])
        user_id = UUID(task_data.get("user_id")) if task_data.get("user_id") else None
        
        # Initialize AI service
        ai_service = AIService()
        
        # Process each deal
        completed_deals = 0
        async for db in get_session():
            # Create repositories and services
            deal_repository = DealRepository(db)
            deal_service = DealService(db, deal_repository)
            
            for deal_id in deal_ids:
                try:
                    # Get deal from database
                    query = select(Deal).filter(Deal.id == UUID(deal_id))
                    result = await db.execute(query)
                    deal = result.scalar_one_or_none()
                    
                    if deal:
                        # Analyze deal
                        analysis = await ai_service.analyze_deal(deal)
                        
                        if analysis:
                            # Store analysis in database or cache
                            await deal_repository.update_deal_analysis(
                                deal_id=UUID(deal_id),
                                analysis=analysis
                            )
                            
                            # Update deal score based on analysis
                            if hasattr(analysis, 'score') and analysis.score is not None:
                                await deal_repository.update_deal_score(
                                    deal_id=UUID(deal_id),
                                    score=float(analysis.score)
                                )
                                
                        # Mark deal as processed
                        completed_deals += 1
                        
                        # Update task progress
                        task_data["completed_deals"] = completed_deals
                        await redis.set(
                            f"task:deal_analysis:{task_id}", 
                            json.dumps(task_data),
                            expire=86400  # 24 hours
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing deal {deal_id}: {str(e)}")
                    # Continue with other deals
        
        # Update task status
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        task_data["status"] = "completed"
        task_data["completed_at"] = end_time.isoformat()
        task_data["processing_time"] = processing_time
        task_data["completed_deals"] = completed_deals
        
        await redis.set(
            f"task:deal_analysis:{task_id}", 
            json.dumps(task_data),
            expire=86400  # 24 hours
        )
        
        # Track the task processing duration as a custom metric
        track_metric(f"deal_analysis_task_duration", "performance")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing deal analysis task {task_id}: {str(e)}")
        return False 