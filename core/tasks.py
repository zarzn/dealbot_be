"""Task definitions module.

This module defines Celery tasks for the AI Agentic Deals System,
including deal monitoring, price analysis, and token processing tasks.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from celery import shared_task
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_log,
    after_log,
    RetryError
)
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.exc import SQLAlchemyError

from core.services.deal import DealService
from core.services.goal import GoalService
from core.services.token import TokenService
from core.services.notification import NotificationService
""" from core.exceptions import (
    DealMonitoringError,
    InsufficientTokensError,
    PriceAnalysisError,
    ExternalServiceError,
    DatabaseError
) 
DO NOT DELETE THIS COMMENT
"""
from core.exceptions import Exception  # We'll use base Exception temporarily
from core.utils.redis import RedisClient
from core.models.deal_score import DealScore
from core.models.goal import GoalStatus
from core.metrics.tasks import TaskMetrics
from core.config import settings

logger = logging.getLogger(__name__)
metrics = TaskMetrics()
redis_client = RedisClient()

@dataclass
class DealAnalysisResult:
    """Data class for deal analysis results."""
    deal_id: str
    score: float
    price_trend: float
    price_volatility: float
    availability_score: float
    seller_score: float
    preference_match: float
    analysis_time: datetime
    is_anomaly: bool = False
    confidence: float = 1.0

def calculate_deal_score(
    deal: Dict[str, Any],
    goal: Dict[str, Any],
    price_history: Optional[List[float]] = None
) -> DealAnalysisResult:
    """Calculate AI-based score for deal using multiple factors with enhanced analysis.
    
    Args:
        deal: Deal information dictionary
        goal: Goal criteria dictionary
        price_history: Optional list of historical prices
        
    Returns:
        DealAnalysisResult object with detailed scoring information
    """
    try:
        # Price comparison (40% weight)
        price_ratio = deal['price'] / goal['max_price']
        price_score = max(0, 1 - price_ratio) * 0.4
        
        # Historical price trend analysis (20% weight)
        trend_score = 0.0
        price_volatility = 0.0
        if price_history and len(price_history) > 1:
            price_series = pd.Series(price_history)
            
            # Calculate trend using exponential weighted average
            trend = price_series.ewm(span=7).mean().pct_change().mean()
            trend_score = (1 - trend) * 0.2
            
            # Calculate price volatility
            price_volatility = price_series.pct_change().std()
            
            # Detect anomalies using z-score
            z_score = abs((deal['price'] - price_series.mean()) / price_series.std())
            is_anomaly = z_score > 2
        else:
            trend_score = 0.1  # Default score if no history
            is_anomaly = False
        
        # Seller reliability (15% weight)
        seller_score = min(1.0, deal.get('seller_rating', 0.5)) * 0.15
        
        # Availability analysis (15% weight)
        availability_score = 0.0
        if deal.get('availability'):
            stock_level = deal.get('stock_level', 0)
            if stock_level > 10:
                availability_score = 0.15
            else:
                availability_score = (stock_level / 10) * 0.15
        
        # User preference matching (10% weight)
        matched_preferences = sum(
            1 for p in goal.get('preferences', [])
            if p in deal.get('features', [])
        )
        total_preferences = len(goal.get('preferences', [])) or 1
        preference_score = (matched_preferences / total_preferences) * 0.1
        
        # Calculate final score
        total_score = min(1.0, max(0.0,
            price_score + trend_score + seller_score +
            availability_score + preference_score
        ))
        
        # Calculate confidence based on data quality
        confidence_factors = [
            1.0 if price_history else 0.7,  # Price history availability
            1.0 if deal.get('seller_rating') else 0.8,  # Seller data availability
            1.0 if deal.get('features') else 0.9  # Feature data availability
        ]
        confidence = np.mean(confidence_factors)
        
        return DealAnalysisResult(
            deal_id=deal['id'],
            score=total_score,
            price_trend=trend_score / 0.2,  # Normalize to 0-1 range
            price_volatility=price_volatility,
            availability_score=availability_score / 0.15,  # Normalize
            seller_score=seller_score / 0.15,  # Normalize
            preference_match=preference_score / 0.1,  # Normalize
            analysis_time=datetime.utcnow(),
            is_anomaly=is_anomaly,
            confidence=confidence
        )
        
    except Exception as e:
        logger.error(f"Error calculating deal score: {str(e)}", exc_info=True)
        metrics.score_calculation_failed(str(e))
        raise PriceAnalysisError(f"Score calculation failed: {str(e)}")

@shared_task(
    bind=True,
    queue='deals_high',
    rate_limit='100/m',
    time_limit=3600,
    soft_time_limit=3300,
    autoretry_for=(SQLAlchemyError,),
    retry_kwargs={'max_retries': 3, 'countdown': 5}
)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((DealMonitoringError, ExternalServiceError)),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARNING)
)
async def monitor_deals(self) -> Dict[str, Any]:
    """Task to monitor deals for active goals with AI scoring and batch processing.
    
    Returns:
        Dict containing task execution statistics
    """
    start_time = datetime.utcnow()
    stats = {
        'goals_processed': 0,
        'deals_analyzed': 0,
        'errors': 0
    }
    
    try:
        logger.info("Starting deal monitoring task")
        metrics.monitoring_task_started()
        
        # Validate token balance
        token_service = TokenService()
        if not await token_service.has_sufficient_balance(
            settings.MONITORING_TOKEN_COST
        ):
            raise InsufficientTokensError(
                required=settings.MONITORING_TOKEN_COST,
                available=await token_service.get_balance()
            )
        
        # Process goals in batches
        batch_size = settings.GOAL_BATCH_SIZE
        offset = 0
        goal_service = GoalService()
        deal_service = DealService()
        
        while True:
            try:
                # Get batch of active goals
                active_goals = await goal_service.get_active_goals(
                    status=GoalStatus.ACTIVE,
                    limit=batch_size,
                    offset=offset
                )
                
                # Check if active_goals is a coroutine and await it if needed
                if hasattr(active_goals, '__await__'):
                    active_goals = await active_goals
                
                if not active_goals:
                    break
                
                # Process each goal in batch
                for goal in active_goals:
                    try:
                        # Get deals for goal
                        deals = await deal_service.get_deals_for_goal(goal)
                        
                        # Check if deals is a coroutine and await it if needed
                        if hasattr(deals, '__await__'):
                            deals = await deals
                        
                        # Analyze each deal
                        analysis_results = []
                        for deal in deals:
                            try:
                                # Get price history
                                price_history = await deal_service.get_price_history(
                                    deal['id'],
                                    days=7
                                )
                                
                                # Check if price_history is a coroutine and await it if needed
                                if hasattr(price_history, '__await__'):
                                    price_history = await price_history
                                
                                # Calculate score
                                result = calculate_deal_score(
                                    deal,
                                    goal,
                                    price_history
                                )
                                analysis_results.append(result)
                                stats['deals_analyzed'] += 1
                                
                                # Update metrics
                                metrics.deal_analyzed(
                                    result.score,
                                    result.confidence,
                                    result.is_anomaly
                                )
                                
                            except Exception as e:
                                logger.error(
                                    f"Error analyzing deal {deal['id']}: {str(e)}",
                                    exc_info=True
                                )
                                stats['errors'] += 1
                                continue
                        
                        # Store results in Redis
                        if analysis_results:
                            redis_key = f"scored_deals:{goal['id']}"
                            redis_result = redis_client.set(
                                redis_key,
                                [result.__dict__ for result in analysis_results],
                                ex=settings.DEAL_CACHE_TTL
                            )
                            # Ensure we await Redis operations
                            if hasattr(redis_result, '__await__'):
                                await redis_result
                        
                        # Process top deals
                        process_result = deal_service.process_top_deals(
                            analysis_results,
                            goal
                        )
                        # Ensure we await process_top_deals if it's a coroutine
                        if hasattr(process_result, '__await__'):
                            await process_result
                        
                        stats['goals_processed'] += 1
                        
                    except Exception as e:
                        logger.error(
                            f"Error processing goal {goal['id']}: {str(e)}",
                            exc_info=True
                        )
                        stats['errors'] += 1
                        continue
                
                offset += batch_size
                
            except Exception as e:
                logger.error(f"Error processing goal batch: {str(e)}", exc_info=True)
                stats['errors'] += 1
                continue
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        stats['execution_time'] = execution_time
        
        # Update metrics
        metrics.monitoring_task_completed(
            stats['goals_processed'],
            stats['deals_analyzed'],
            stats['errors'],
            execution_time
        )
        
        logger.info(
            "Completed deal monitoring task",
            extra={'stats': stats}
        )
        return stats
        
    except Exception as e:
        metrics.monitoring_task_failed(str(e))
        logger.error(f"Deal monitoring task failed: {str(e)}", exc_info=True)
        raise DealMonitoringError(f"Deal monitoring failed: {str(e)}")

@shared_task(
    bind=True,
    queue='deals',
    rate_limit='50/m',
    time_limit=1800,
    soft_time_limit=1700
)
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(PriceAnalysisError),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARNING)
)
async def update_prices(self) -> Dict[str, Any]:
    """Task to update prices with trend analysis and anomaly detection.
    
    Returns:
        Dict containing task execution statistics
    """
    start_time = datetime.utcnow()
    stats = {
        'deals_processed': 0,
        'anomalies_detected': 0,
        'errors': 0
    }
    
    try:
        logger.info("Starting price update task")
        metrics.price_update_started()
        
        # Get tracked deals
        deal_service = DealService()
        tracked_deals = await deal_service.get_tracked_deals()
        
        # Process each deal
        for deal in tracked_deals:
            try:
                # Get complete price history
                price_history = await deal_service.get_price_history(
                    deal['id'],
                    days=30
                )
                
                if not price_history or len(price_history) < 3:
                    continue
                
                # Convert to pandas Series with datetime index
                price_series = pd.Series(
                    data=price_history,
                    index=pd.date_range(
                        start=datetime.utcnow() - timedelta(days=30),
                        periods=len(price_history),
                        freq='D'
                    )
                )
                
                # Calculate statistics
                ewm = price_series.ewm(span=7)
                moving_avg = ewm.mean()
                std_dev = price_series.rolling(window=7).std()
                
                # Detect anomalies using multiple methods
                current_price = deal['current_price']
                
                # Z-score method
                z_score = abs((current_price - moving_avg[-1]) / std_dev[-1])
                z_score_anomaly = z_score > 2
                
                # Percent change method
                pct_change = abs(
                    (current_price - moving_avg[-1]) / moving_avg[-1]
                )
                pct_change_anomaly = pct_change > 0.15
                
                # Combined anomaly detection
                is_anomaly = z_score_anomaly and pct_change_anomaly
                
                if is_anomaly:
                    stats['anomalies_detected'] += 1
                
                # Calculate additional metrics
                volatility = price_series.pct_change().std()
                trend = price_series.pct_change().mean()
                
                # Update deal with analysis results
                await deal_service.update_deal_price_analysis(
                    deal['id'],
                    {
                        'moving_average': float(moving_avg[-1]),
                        'std_dev': float(std_dev[-1]),
                        'volatility': float(volatility),
                        'trend': float(trend),
                        'z_score': float(z_score),
                        'percent_change': float(pct_change),
                        'is_anomaly': is_anomaly,
                        'last_analyzed': datetime.utcnow()
                    }
                )
                
                # Send notifications for significant price changes
                if is_anomaly:
                    await NotificationService.send_price_alert(
                        deal_id=deal['id'],
                        price_change=pct_change,
                        is_increase=current_price > moving_avg[-1]
                    )
                
                stats['deals_processed'] += 1
                metrics.price_analyzed(
                    volatility,
                    trend,
                    is_anomaly
                )
                
            except Exception as e:
                logger.error(
                    f"Error analyzing prices for deal {deal['id']}: {str(e)}",
                    exc_info=True
                )
                stats['errors'] += 1
                continue
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        stats['execution_time'] = execution_time
        
        # Update metrics
        metrics.price_update_completed(
            stats['deals_processed'],
            stats['anomalies_detected'],
            stats['errors'],
            execution_time
        )
        
        logger.info(
            "Completed price update task",
            extra={'stats': stats}
        )
        return stats
        
    except Exception as e:
        metrics.price_update_failed(str(e))
        logger.error(f"Price update task failed: {str(e)}", exc_info=True)
        raise PriceAnalysisError(f"Price analysis failed: {str(e)}")

@shared_task(
    bind=True,
    queue='deals',
    rate_limit='100/m'
)
async def cleanup_expired_deals(self) -> Dict[str, Any]:
    """Task to clean up expired deals and maintain database health."""
    start_time = datetime.utcnow()
    stats = {
        'deals_cleaned': 0,
        'errors': 0
    }
    
    try:
        logger.info("Starting deal cleanup task")
        
        # Get expired deals
        deal_service = DealService()
        expired_deals = await deal_service.get_expired_deals()
        
        for deal in expired_deals:
            try:
                # Archive deal data
                await deal_service.archive_deal(deal['id'])
                
                # Remove from active monitoring
                await deal_service.remove_from_monitoring(deal['id'])
                
                # Clear cached data
                await redis_client.delete(f"deal:{deal['id']}")
                
                stats['deals_cleaned'] += 1
                
            except Exception as e:
                logger.error(
                    f"Error cleaning up deal {deal['id']}: {str(e)}",
                    exc_info=True
                )
                stats['errors'] += 1
                continue
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        stats['execution_time'] = execution_time
        
        logger.info(
            "Completed deal cleanup task",
            extra={'stats': stats}
        )
        return stats
        
    except Exception as e:
        logger.error(f"Deal cleanup task failed: {str(e)}", exc_info=True)
        raise
