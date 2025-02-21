"""Deal service module.

This module provides deal-related services for the AI Agentic Deals System.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
import logging
import json
import asyncio
from fastapi import BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import httpx
from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import joinedload

from core.models.user import User
from core.models.tracked_deal import TrackedDeal
from core.models.deal import (
    Deal,
    DealCreate,
    DealUpdate,
    DealStatus,
    DealPriority,
    DealSource,
    DealSearchFilters,
    DealResponse,
    DealFilter,
    DealSearch,
    PriceHistory,
    AIAnalysis
)
from core.repositories.deal import DealRepository
from core.utils.redis import get_redis_client
from core.exceptions import (
    DealError,
    DealNotFoundError,
    InvalidDealDataError,
    DealExpirationError,
    DealPriceError,
    DealValidationError,
    DealProcessingError,
    DealScoreError,
    APIError,
    APIRateLimitError,
    APIServiceUnavailableError,
    DatabaseError,
    CacheOperationError,
    ExternalServiceError,
    ValidationError,
    NetworkError,
    DataProcessingError,
    RepositoryError,
    AIServiceError,
    RateLimitExceededError,
    TokenError
)

from core.config import settings
from core.utils.ecommerce import (
    AmazonAPI,
    WalmartAPI,
    EcommerceAPIError
)
from core.services.token import TokenService
from core.services.crawler import WebCrawler
from core.utils.llm import get_llm_instance
from core.services.base import BaseService
from core.services.ai import AIService

logger = logging.getLogger(__name__)

# Configuration constants
API_CALLS_PER_MINUTE = 60
DEAL_ANALYSIS_RETRIES = 3
MONITORING_INTERVAL_MINUTES = 30
CACHE_TTL_BASIC = 7200  # 2 hours
CACHE_TTL_FULL = 3600   # 1 hour
CACHE_TTL_PRICE_HISTORY = 86400  # 24 hours
CACHE_TTL_SEARCH = 600  # 10 minutes
MAX_BATCH_SIZE = 100
MIN_RETRY_DELAY = 4  # seconds
MAX_RETRY_DELAY = 10  # seconds

class DealService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.repository = DealRepository(session)
        self.redis = get_redis_client()
        self.llm_chain = self._initialize_llm_chain()
        self.scheduler = AsyncIOScheduler()
        self.amazon_api = AmazonAPI()
        self.walmart_api = WalmartAPI()
        self.token_service = TokenService(session)
        self.crawler = WebCrawler()
        self._initialize_scheduler()
        self._setup_rate_limiting()
        self._setup_error_handlers()
        self._background_tasks = None
        self.ai_service = AIService()

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

    def _initialize_llm_chain(self) -> LLMChain:
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
        return LLMChain(llm=get_llm_instance(), prompt=prompt_template)

    @sleep_and_retry
    @limits(calls=API_CALLS_PER_MINUTE, period=60)
    async def create_deal(
        self,
        goal_id: UUID,
        title: str,
        description: Optional[str],
        price: Decimal,
        original_price: Optional[Decimal],
        currency: str,
        source: str,
        url: str,
        image_url: Optional[str],
        deal_metadata: Optional[Dict[str, Any]] = None,
        price_metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
        status: DealStatus = DealStatus.ACTIVE
    ) -> Deal:
        """Create a new deal"""
        try:
            deal = Deal(
                goal_id=goal_id,
                title=title,
                description=description,
                price=price,
                original_price=original_price,
                currency=currency,
                source=source,
                url=url,
                image_url=image_url,
                deal_metadata=deal_metadata,
                price_metadata=price_metadata,
                expires_at=expires_at,
                status=status
            )
            
            # Calculate AI score with retry mechanism
            score = await self._calculate_deal_score(deal)
            
            # Add score to deal data
            deal_data_dict = deal.dict()
            deal_data_dict['score'] = score
            
            # Create deal in database
            deal = self.repository.create(deal_data_dict)
            
            # Cache deal data with separate TTLs
            self._cache_deal(deal)
            
            logger.info(f"Successfully created deal {deal.id} with score {score}")
            return deal
            
        except RateLimitExceededError:
            logger.warning("Rate limit exceeded while creating deal")
            raise
        except AIServiceError as e:
            logger.error(f"AI service error while creating deal: {str(e)}")
            raise
        except ExternalServiceError as e:
            logger.error(f"External service error while creating deal: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while creating deal: {str(e)}")
            raise ExternalServiceError("Failed to create deal")

    @retry(stop=stop_after_attempt(DEAL_ANALYSIS_RETRIES), 
           wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_deal(self, deal_id: str) -> Deal:
        """Get deal by ID with cache fallback and retry mechanism"""
        try:
            # Try to get from cache first
            cached_deal = self._get_cached_deal(deal_id)
            if cached_deal:
                return cached_deal
                
            # Fallback to database
            deal = self.repository.get_by_id(deal_id)
            if not deal:
                raise DealNotFoundError(f"Deal {deal_id} not found")
                
            # Cache the deal
            self._cache_deal(deal)
            
            return deal
        except Exception as e:
            logger.error(f"Failed to get deal: {str(e)}")
            raise

    async def process_deals_batch(self, deals: List[DealCreate]) -> List[Deal]:
        """Process multiple deals in batch with background tasks and rate limiting
        
        Args:
            deals: List of DealCreate objects to process
            
        Returns:
            List[Deal]: List of successfully processed deals
            
        Raises:
            RateLimitExceededError: If API rate limit is exceeded
            ExternalServiceError: If external service fails
        """
        processed_deals = []
        batch_size = min(len(deals), MAX_BATCH_SIZE)
        
        try:
            for i, deal_data in enumerate(deals[:batch_size]):
                try:
                    # Process each deal in background with rate limiting
                    self.add_background_task(
                        self._process_single_deal_with_retry, 
                        deal_data
                    )
                    processed_deals.append(deal_data)
                    
                    # Rate limit control
                    if (i + 1) % 10 == 0:
                        await asyncio.sleep(1)
                        
                except RateLimitExceededError:
                    logger.warning("Rate limit reached, pausing batch processing")
                    await asyncio.sleep(60)  # Wait 1 minute before continuing
                    continue
                except Exception as e:
                    logger.error(f"Failed to process deal: {str(e)}")
                    continue
                    
            logger.info(f"Successfully processed {len(processed_deals)} deals in batch")
            return processed_deals
            
        except Exception as e:
            logger.error(f"Failed to process batch of deals: {str(e)}")
            raise ExternalServiceError("Failed to process batch of deals")

    @retry(stop=stop_after_attempt(DEAL_ANALYSIS_RETRIES),
           wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _process_single_deal_with_retry(self, deal_data: DealCreate) -> Deal:
        """Process single deal with retry mechanism"""
        return await self._process_single_deal(deal_data)

    async def _process_single_deal(self, deal_data: DealCreate) -> Deal:
        """Process a single deal with AI scoring, validation, and analysis"""
        try:
            # Apply AI scoring and analysis
            score = await self._calculate_deal_score(deal_data)
            analysis = await self._analyze_deal(deal_data)
            
            # Create deal with score and analysis
            deal_data_dict = deal_data.dict()
            deal_data_dict.update({
                'score': score,
                'analysis': analysis
            })
            
            deal = await self.create_deal(deal_data_dict)
            return deal
        except Exception as e:
            logger.error(f"Failed to process single deal: {str(e)}")
            raise

    async def _monitor_deals(self) -> None:
        """Background task to monitor deals from e-commerce APIs"""
        try:
            # Get active goals from database
            active_goals = self.repository.get_active_goals()
            
            # Try to fetch deals from APIs first
            try:
                amazon_deals = await self._fetch_deals_from_api(self.amazon_api, active_goals)
                walmart_deals = await self._fetch_deals_from_api(self.walmart_api, active_goals)
                all_deals = amazon_deals + walmart_deals
            except EcommerceAPIError:
                # Fallback to web scraping if APIs fail
                logger.warning("API failed, falling back to web scraping")
                all_deals = []
                for goal in active_goals:
                    try:
                        scraped_deals = await self.crawler.scrape_fallback(goal['item_category'])
                        all_deals.extend(scraped_deals)
                    except Exception as e:
                        logger.error(f"Failed to scrape deals for goal {goal['id']}: {str(e)}")
                        continue
            await self._process_and_store_deals(all_deals)
            
        except Exception as e:
            logger.error(f"Failed to monitor deals: {str(e)}")

    async def _fetch_deals_from_api(self, api: Any, goals: List[Dict]) -> List[Dict]:
        """Fetch deals from e-commerce API based on active goals"""
        try:
            deals = []
            for goal in goals:
                params = self._build_search_params(goal)
                api_deals = await api.search_deals(params)
                deals.extend(api_deals)
            return deals
        except EcommerceAPIError as e:
            logger.error(f"Failed to fetch deals from {api.__class__.__name__}: {str(e)}")
            return []

    def _build_search_params(self, goal: Dict) -> Dict:
        """Build search parameters from goal constraints"""
        return {
            'keywords': goal.get('keywords', []),
            'price_range': (goal.get('min_price'), goal.get('max_price')),
            'brands': goal.get('brands', []),
            'categories': goal.get('categories', [])
        }

    async def _process_and_store_deals(self, deals: List[Dict]) -> None:
        """Process and store fetched deals"""
        for deal in deals:
            try:
                deal_data = DealCreate(
                    product_name=deal['product_name'],
                    description=deal.get('description'),
                    price=deal['price'],
                    original_price=deal.get('original_price'),
                    currency=deal.get('currency', 'USD'),
                    source=deal['source'],
                    url=deal['url'],
                    image_url=deal.get('image_url'),
                    expires_at=deal.get('expires_at'),
                    metadata=deal.get('metadata', {})
                )
                await self.create_deal(deal_data)
            except Exception as e:
                logger.error(f"Failed to process deal: {str(e)}")

    async def _calculate_deal_score(self, deal_data: DealCreate) -> float:
        """Calculate AI score for a deal using multiple factors and store score history"""
        try:
            # Get historical data and source reliability
            price_history = self.repository.get_price_history(
                deal_data.product_name,
                days=30
            )
            source_reliability = self._get_source_reliability(deal_data.source)
            
            # Calculate base score from LLM
            llm_result = await self.llm_chain.arun({
                'product_name': deal_data.product_name,
                'description': deal_data.description or '',
                'price': deal_data.price,
                'source': deal_data.source
            })
            base_score = float(llm_result.split('Score:')[1].split('/')[0].strip())
            
            # Apply modifiers based on additional factors
            final_score = self._apply_score_modifiers(
                base_score,
                price_history,
                source_reliability,
                deal_data
            )
            final_score = min(max(final_score, 0), 100)  # Ensure score is between 0-100
            
            # Calculate moving average and standard deviation
            previous_scores = self.repository.get_deal_scores(deal_data.product_name)
            moving_avg = self._calculate_moving_average(previous_scores + [final_score])
            std_dev = self._calculate_std_dev(previous_scores + [final_score])
            
            # Determine if score is an anomaly
            is_anomaly = self._detect_score_anomaly(final_score, moving_avg, std_dev)
            
            # Store score in DealScore table
            score_data = {
                'score': final_score,
                'moving_average': moving_avg,
                'std_dev': std_dev,
                'is_anomaly': is_anomaly
            }
            self.repository.create_deal_score(deal_data.product_name, score_data)
            
            return final_score
            
        except Exception as e:
            logger.error(f"Failed to calculate deal score: {str(e)}")
            raise AIServiceError("Failed to calculate deal score using AI")

    def _calculate_moving_average(self, scores: List[float]) -> float:
        """Calculate moving average of scores"""
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def _calculate_std_dev(self, scores: List[float]) -> float:
        """Calculate standard deviation of scores"""
        if len(scores) < 2:
            return 0.0
        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / (len(scores) - 1)
        return variance ** 0.5

    def _detect_score_anomaly(self, score: float, moving_avg: float, std_dev: float) -> bool:
        """Detect if score is an anomaly based on historical data"""
        if std_dev == 0:
            return False
        z_score = abs((score - moving_avg) / std_dev)
        return z_score > 2.0  # Consider score an anomaly if it's more than 2 std devs from mean

    def _apply_score_modifiers(self, base_score: float, price_history: List[Dict], 
                             source_reliability: float, deal_data: DealCreate) -> float:
        """Apply modifiers to base score based on additional factors"""
        # Price trend modifier
        price_trend = self._calculate_price_trend(price_history)
        trend_modifier = {
            'decreasing': 1.1,
            'stable': 1.0,
            'increasing': 0.9
        }.get(price_trend, 1.0)
        
        # Source reliability modifier
        source_modifier = source_reliability
        
        # Price competitiveness modifier
        if deal_data.original_price:
            discount = (deal_data.original_price - deal_data.price) / deal_data.original_price
            discount_modifier = min(max(1.0 + discount, 0.8), 1.2)
        else:
            discount_modifier = 1.0
            
        # Apply modifiers
        final_score = base_score * trend_modifier * source_modifier * discount_modifier
        return final_score

    async def _analyze_deal(self, deal_data: DealCreate) -> Dict:
        """Perform comprehensive deal analysis"""
        try:
            # Get price history
            price_history = self.repository.get_price_history(
                deal_data.product_name,
                days=30
            )
            
            # Calculate price trends
            price_trend = self._calculate_price_trend(price_history)
            
            return {
                'price_history': price_history,
                'price_trend': price_trend,
                'source_reliability': self._get_source_reliability(deal_data.source)
            }
        except Exception as e:
            logger.error(f"Failed to analyze deal: {str(e)}")
            raise

    def _calculate_price_trend(self, price_history: List[Dict]) -> str:
        """Calculate price trend based on historical data"""
        if not price_history:
            return 'stable'
            
        prices = [entry['avg_price'] for entry in price_history]
        if prices[-1] < prices[0]:
            return 'decreasing'
        elif prices[-1] > prices[0]:
            return 'increasing'
        return 'stable'

    def _get_source_reliability(self, source: str) -> float:
        """Get source reliability score from cache or default"""
        try:
            score = self.redis.get(f"source:{source}")
            return float(score) if score else 0.8  # Default score
        except Exception as e:
            logger.error(f"Failed to get source reliability: {str(e)}")
            return 0.8

    def _cache_deal(self, deal: Deal) -> None:
        """Cache deal data in Redis with extended information and separate TTLs
        
        Args:
            deal: Deal object to cache
            
        Raises:
            RedisError: If caching operation fails
        """
        try:
            # Prepare cache data
            cache_data = {
                'deal': deal.json(),
                'score': deal.score,
                'analysis': deal.analysis,
                'price_history': self.repository.get_price_history(deal.product_name),
                'source_reliability': self._get_source_reliability(deal.source),
                'last_updated': datetime.now().isoformat()
            }
            
            # Cache different components with appropriate TTLs
            with self.redis.pipeline() as pipe:
                pipe.set(f"deal:{deal.id}:full", cache_data, ex=CACHE_TTL_FULL)
                pipe.set(f"deal:{deal.id}:basic", deal.json(), ex=CACHE_TTL_BASIC)
                pipe.set(
                    f"deal:{deal.id}:price_history",
                    json.dumps(cache_data['price_history']),
                    ex=CACHE_TTL_PRICE_HISTORY
                )
                pipe.execute()
                
            logger.debug(f"Successfully cached deal {deal.id}")
            
        except Exception as e:
            logger.error(f"Failed to cache deal {deal.id}: {str(e)}")
            raise

    def _get_cached_deal(self, deal_id: str) -> Optional[Deal]:
        """Get cached deal from Redis with extended information"""
        try:
            # Try to get full cached data first
            cached_data = self.redis.get(f"deal:{deal_id}:full")
            if cached_data:
                data = json.loads(cached_data)
                return Deal.parse_raw(data['deal'])
            
            # Fallback to basic cached data
            basic_data = self.redis.get(f"deal:{deal_id}:basic")
            if basic_data:
                return Deal.parse_raw(basic_data)
                
            return None
        except Exception as e:
            logger.error(f"Failed to get cached deal: {str(e)}")
            raise

    async def search_deals(
        self,
        search: DealSearch,
        user_id: Optional[UUID] = None
    ) -> List[DealResponse]:
        """
        Search for deals based on criteria
        """
        query = select(Deal).options(
            joinedload(Deal.price_points),
            joinedload(Deal.tracked_by_users)
        )

        if search.query:
            query = query.filter(Deal.title.ilike(f"%{search.query}%"))
        
        if search.category:
            query = query.filter(Deal.category == search.category)
        
        if search.min_price is not None:
            query = query.filter(Deal.price >= search.min_price)
        
        if search.max_price is not None:
            query = query.filter(Deal.price <= search.max_price)

        # Add sorting
        if search.sort_by == "price":
            query = query.order_by(
                Deal.price.desc() if search.sort_order == "desc" else Deal.price.asc()
            )
        elif search.sort_by == "date":
            query = query.order_by(
                Deal.found_at.desc() if search.sort_order == "desc" else Deal.found_at.asc()
            )

        # Add pagination
        query = query.offset(search.offset).limit(search.limit)

        deals = await self.session.execute(query)
        deals = deals.scalars().unique().all()

        # Convert to response models
        return [
            await self._to_response(deal, user_id)
            for deal in deals
        ]

    async def get_deal(
        self,
        deal_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Optional[DealResponse]:
        """
        Get a specific deal by ID
        """
        query = select(Deal).options(
            joinedload(Deal.price_points),
            joinedload(Deal.tracked_by_users)
        ).filter(Deal.id == deal_id)

        deal = await self.session.execute(query)
        deal = deal.scalar_one_or_none()

        if not deal:
            return None

        return await self._to_response(deal, user_id)

    async def get_deal_analysis(self, deal_id: UUID) -> Optional[AIAnalysis]:
        """
        Get AI analysis for a deal
        """
        deal = await self.get_deal(deal_id)
        if not deal:
            return None

        return await self.ai_service.analyze_deal(deal)

    async def get_price_history(
        self,
        deal_id: UUID,
        days: int = 30
    ) -> List[PriceHistory]:
        """
        Get price history for a deal
        """
        query = select(Deal).options(
            joinedload(Deal.price_points)
        ).filter(Deal.id == deal_id)

        deal = await self.session.execute(query)
        deal = deal.scalar_one_or_none()

        if not deal:
            return []

        # Convert price points to PriceHistory
        return [
            PriceHistory(
                price=point.price,
                currency=point.currency,
                timestamp=point.timestamp,
                source=point.source,
                meta_data=point.meta_data
            )
            for point in deal.price_points
        ]

    async def track_deal(self, deal_id: UUID, user_id: UUID) -> None:
        """
        Track a deal for a user
        """
        tracked_deal = TrackedDeal(
            deal_id=deal_id,
            user_id=user_id
        )
        self.session.add(tracked_deal)
        await self.session.commit()

    async def untrack_deal(self, deal_id: UUID, user_id: UUID) -> None:
        """
        Untrack a deal for a user
        """
        query = select(TrackedDeal).filter(
            TrackedDeal.deal_id == deal_id,
            TrackedDeal.user_id == user_id
        )
        tracked_deal = await self.session.execute(query)
        tracked_deal = tracked_deal.scalar_one_or_none()

        if tracked_deal:
            await self.session.delete(tracked_deal)
            await self.session.commit()

    async def _to_response(
        self,
        deal: Deal,
        user_id: Optional[UUID] = None
    ) -> DealResponse:
        """
        Convert a Deal model to a DealResponse
        """
        # Get price history
        price_history = [
            PriceHistory(
                price=point.price,
                currency=point.currency,
                timestamp=point.timestamp,
                source=point.source,
                meta_data=point.meta_data
            )
            for point in deal.price_points
        ]

        # Check if deal is tracked by user
        is_tracked = False
        if user_id:
            is_tracked = any(
                tracked.user_id == user_id
                for tracked in deal.tracked_by_users
            )

        # Get price extremes
        prices = [point.price for point in deal.price_points]
        lowest_price = min(prices) if prices else None
        highest_price = max(prices) if prices else None

        # Get AI analysis
        ai_analysis = await self.ai_service.analyze_deal(deal)

        return DealResponse(
            id=deal.id,
            title=deal.title,
            description=deal.description,
            url=deal.url,
            price=deal.price,
            original_price=deal.original_price,
            currency=deal.currency,
            source=deal.source,
            image_url=deal.image_url,
            category=deal.category,
            seller_info=deal.seller_info,
            shipping_info=deal.shipping_info,
            is_tracked=is_tracked,
            lowest_price=lowest_price,
            highest_price=highest_price,
            price_history=price_history,
            ai_analysis=ai_analysis,
            found_at=deal.found_at,
            expires_at=deal.expires_at,
            status=deal.status
        )

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True
