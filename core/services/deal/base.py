"""Base Deal service module.

This module provides the base DealService class and initialization methods.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from fastapi import BackgroundTasks
from pydantic import ConfigDict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from langchain_core.prompts import PromptTemplate
import time

from core.models.deal import Deal
from core.services.base import BaseService
from core.repositories.deal import DealRepository
from core.utils.redis import get_redis_client
from core.utils.llm import create_llm_chain
from core.utils.ecommerce import AmazonAPI, WalmartAPI
from core.config import settings
from core.services.token import TokenService
from core.services.crawler import WebCrawler
from core.services.redis import get_redis_service
from .tracking import DealTrackingMixin  # Import the tracking mixin

logger = logging.getLogger(__name__)

# Configuration constants
MONITORING_INTERVAL_MINUTES = 30
CACHE_TTL_BASIC = 7200  # 2 hours
CACHE_TTL_FULL = 3600   # 1 hour
CACHE_TTL_PRICE_HISTORY = 86400  # 24 hours
CACHE_TTL_SEARCH = 600  # 10 minutes


class DealService(BaseService[Deal, Any, Any], DealTrackingMixin):
    """Deal service for managing deal-related operations."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    model = Deal
    _analysis_cache = {}  # In-memory cache for deal analysis when Redis is not available
    
    def __init__(self, session: AsyncSession, redis_service: Optional[Redis] = None):
        """Initialize the deal service.
        
        Args:
            session: The database session
            redis_service: Optional Redis service for caching
        """
        super().__init__(session=session, redis_service=redis_service)
        self._repository = DealRepository(session)
        self.session = session  # Explicitly set the session attribute
        self.llm_chain = self._initialize_llm_chain()
        self.scheduler = AsyncIOScheduler()
        
        # Safely handle Amazon API keys
        access_key = ""
        if hasattr(settings, "AMAZON_ACCESS_KEY"):
            if hasattr(settings.AMAZON_ACCESS_KEY, "get_secret_value"):
                access_key = settings.AMAZON_ACCESS_KEY.get_secret_value()
            else:
                access_key = settings.AMAZON_ACCESS_KEY or ""
                
        secret_key = ""
        if hasattr(settings, "AMAZON_SECRET_KEY"):
            if hasattr(settings.AMAZON_SECRET_KEY, "get_secret_value"):
                secret_key = settings.AMAZON_SECRET_KEY.get_secret_value()
            else:
                secret_key = settings.AMAZON_SECRET_KEY or ""
        
        self.amazon_api = AmazonAPI(
            access_key=access_key,
            secret_key=secret_key,
            partner_tag=settings.AMAZON_PARTNER_TAG,
            region=settings.AMAZON_COUNTRY
        )
        
        # Use getattr with defaults for settings that might not be present
        walmart_api_key = getattr(settings, "WALMART_CLIENT_ID", None)
        if walmart_api_key and hasattr(walmart_api_key, "get_secret_value"):
            walmart_api_key = walmart_api_key.get_secret_value()
        
        max_retries = getattr(settings, "MAX_RETRIES", 3)
        request_timeout = getattr(settings, "REQUEST_TIMEOUT", 30)
        walmart_rate_limit = getattr(settings, "WALMART_RATE_LIMIT", 200)
        
        self.walmart_api = WalmartAPI(
            api_key=walmart_api_key or "",
            max_retries=max_retries,
            timeout=request_timeout,
            rate_limit=walmart_rate_limit
        )
        
        self.token_service = TokenService(session)
        self.crawler = WebCrawler()
        self._initialize_scheduler()
        self._setup_rate_limiting()
        self._setup_error_handlers()
        self._background_tasks = None
        self.ai_service = None

    async def initialize(self):
        """Initialize service dependencies."""
        if self._redis is None:
            self._redis = await get_redis_client()
            
        if self.ai_service is None:
            try:
                # Lazy import to avoid circular dependencies
                from core.services.ai import get_ai_service
                
                # Track initialization attempts at class level to avoid excessive retries
                if not hasattr(DealService, '_ai_service_init_attempted'):
                    logger.debug("First AIService initialization attempt in DealService")
                    DealService._ai_service_init_attempted = True
                    DealService._last_ai_service_attempt = time.time()
                    DealService._ai_service_retries = 0
                    self.ai_service = await get_ai_service()
                    
                    # Only log once if AI service is initialized successfully
                    if self.ai_service:
                        logger.info("AIService initialized successfully in DealService")
                        DealService._ai_service_logged = True
                    else:
                        logger.warning("AIService initialization returned None in DealService")
                elif not self.ai_service:
                    # Implement backoff for retry attempts
                    current_time = time.time()
                    last_attempt = getattr(DealService, '_last_ai_service_attempt', 0)
                    time_since_last = current_time - last_attempt
                    
                    # Exponential backoff: 1 min, 5 mins, 15 mins max
                    retry_count = getattr(DealService, '_ai_service_retries', 0)
                    retry_threshold = min(900, 60 * (2 ** min(3, retry_count)))
                    
                    if time_since_last > retry_threshold:
                        # Update retry counter and timestamp
                        DealService._ai_service_retries = retry_count + 1
                        DealService._last_ai_service_attempt = current_time
                        
                        logger.info(f"Retrying AIService initialization (attempt #{DealService._ai_service_retries})")
                        self.ai_service = await get_ai_service()
                        
                        if self.ai_service:
                            logger.info(f"AIService initialized successfully after {DealService._ai_service_retries} retries")
                            DealService._ai_service_logged = True
                        else:
                            logger.warning(f"AIService initialization still returning None after {DealService._ai_service_retries} retries")
            except Exception as e:
                logger.error(f"Error initializing AIService in DealService: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                # Continue without AI service - the service should gracefully handle missing AI capabilities

    def set_background_tasks(self, background_tasks: Optional[BackgroundTasks]) -> None:
        """Set the background tasks instance.
        
        Args:
            background_tasks: FastAPI BackgroundTasks instance
        """
        self._background_tasks = background_tasks

    def add_background_task(self, func: Any, *args: Any, **kwargs: Any) -> None:
        """Add a task to be executed in the background.
        
        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Raises:
            ValueError: If background_tasks is not initialized
        """
        if self._background_tasks is None:
            raise ValueError("Background tasks not initialized")
        self._background_tasks.add_task(func, *args, **kwargs)

    def _initialize_scheduler(self) -> None:
        """Initialize scheduled background tasks for deal monitoring"""
        self.scheduler.add_job(
            self._monitor_deals,
            trigger=IntervalTrigger(minutes=MONITORING_INTERVAL_MINUTES),
            max_instances=1
        )
        self.scheduler.start()

    async def _monitor_deals(self) -> None:
        """Background task to monitor deals for changes and notify users.
        
        This method runs periodically to:
        1. Check for price changes
        2. Update expired deals
        3. Refresh deal data from sources
        4. Match new deals with user goals
        """
        from core.services.deal.search.monitoring import monitor_deals
        try:
            await monitor_deals(self)
        except Exception as e:
            logger.error(f"Error in deal monitoring: {str(e)}")

    def _setup_rate_limiting(self) -> None:
        """Initialize rate limiting configuration"""
        self.rate_limiter = {
            'last_call': datetime.now(),
            'call_count': 0
        }

    def _setup_error_handlers(self) -> None:
        """Initialize error handlers"""
        self.error_handlers = {
            'retry_count': 0,
            'last_error': None
        }

    def _initialize_llm_chain(self):
        """Initialize LLM chain for deal analysis"""
        prompt_template = PromptTemplate(
            input_variables=["product_name", "description", "price", "source"],
            template="""
            Analyze this deal and provide a score from 0-100 based on:
            - Product quality (based on description)
            - Price competitiveness
            - Source reliability
            - Historical pricing trends
            
            Product: {product_name}
            Description: {description}
            Price: {price}
            Source: {source}
            
            Provide score and brief reasoning:
            """
        )
        # Create a chain without the RunnablePassthrough wrapping - let the raw variables be passed
        return create_llm_chain(prompt_template)

    # Import methods from the different modules
    from .core import (
        create_deal,
        get_deal,
        process_deals_batch,
        _process_single_deal_with_retry,
        _process_single_deal,
        update_deal,
        delete_deal,
        list_deals,
        get_deals,
        get_deal_by_id,
        get_recent_deals
    )
    
    from .search import (
        search_deals,
        perform_realtime_scraping,
        filter_deals,
        create_deal_from_product,
        monitor_deals,
        fetch_deals_from_api,
        build_search_params,
        process_and_store_deals,
        is_valid_market_category,
        discover_deal,
        search_products
    )
    
    from .price import (
        add_price_point,
        get_price_history,
        analyze_price_trends,
        _calculate_price_trend
    )
    
    from .analysis import (
        _analyze_deal,
        _calculate_deal_score,
        _get_source_reliability,
        analyze_deal_with_ai,
        get_deal_analysis,
        _apply_score_modifiers,
        _calculate_moving_average,
        _calculate_std_dev,
        _detect_score_anomaly,
        _update_deal_score
    )
    
    from .comparison import (
        compare_deals,
        _compare_by_price,
        _compare_by_features,
        _compare_by_value,
        _compare_overall,
        _extract_features_from_description
    )
    
    from .validation import (
        validate_deal,
        validate_deal_data,
        _validate_url,
        _validate_price
    )
    
    from .flash_deals import (
        create_flash_deal,
        _send_flash_deal_notifications
    )
    
    from .monitoring import (
        refresh_deal,
        _deal_to_dict,
        _convert_deal_to_dict,
        _safe_copy_dict,
        check_expired_deals
    )
    
    from .goals import (
        match_with_goals,
        get_matched_goals,
        _matches_goal_criteria
    )
    
    from .creation import (
        create_deal_from_dict,
        _create_deal_from_scraped_data,
        _convert_to_response
    )
    
    from .cache import (
        _cache_deal,
        _get_cached_deal
    ) 