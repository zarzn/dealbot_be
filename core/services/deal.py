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

from core.models.deal import (
    Deal,
    DealCreate,
    DealUpdate,
    DealStatus,
    DealPriority,
    DealSource,
    DealSearchFilters,
    DealResponse,
    DealFilter
)
from core.models.goal import Goal
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

class DealService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DealRepository(db)
        self.redis = get_redis_client()
        self.llm_chain = self._initialize_llm_chain()
        self.scheduler = AsyncIOScheduler()
        self.amazon_api = AmazonAPI()
        self.walmart_api = WalmartAPI()
        self.token_service = TokenService(db)
        self.crawler = WebCrawler()
        self._initialize_scheduler()
        self._setup_rate_limiting()
        self._setup_error_handlers()
        self._background_tasks = None

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
        query: str,
        limit: int = 10,
        filters: Optional[DealSearchFilters] = None
    ) -> List[Deal]:
        """
        Search for deals with caching and rate limiting.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            filters: Optional search filters
            
        Returns:
            List of matching deals
        """
        try:
            # Generate cache key based on query and filters
            cache_key = f"deal_search:{query}:{limit}"
            if filters:
                cache_key += f":{filters.json()}"
                
            # Try to get cached results first
            cached_results = await self._get_cached_search(cache_key)
            if cached_results:
                logger.info(f"Cache hit for search query: {query}")
                return cached_results
                
            # Apply rate limiting
            await self._check_rate_limit("search")
            
            # Perform search with filters
            results = await self._search_with_rate_limit(query, limit, filters)
            
            # Cache the results
            await self._cache_search(cache_key, results)
            
            return results
            
        except RateLimitExceededError as e:
            logger.error(f"Rate limit exceeded for search: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error in search_deals: {str(e)}")
            raise DealError(f"Failed to search deals: {str(e)}")

    async def _check_rate_limit(self, operation: str) -> None:
        """Check rate limiting for specific operations."""
        key = f"rate_limit:{operation}"
        current = await self.redis.incr(key)
        
        if current == 1:
            await self.redis.expire(key, 60)  # Reset after 1 minute
            
        if current > settings.RATE_LIMIT_PER_MINUTE:
            raise RateLimitExceededError(
                f"Rate limit exceeded for {operation}. Try again later."
            )
            
    async def _search_with_rate_limit(
        self,
        query: str,
        limit: int,
        filters: Optional[DealSearchFilters] = None
    ) -> List[Deal]:
        """Perform rate-limited search operation."""
        try:
            # Build base query
            base_query = self.repository.build_search_query(query)
            
            # Apply filters if provided
            if filters:
                base_query = self._apply_search_filters(base_query, filters)
                
            # Execute query with limit
            results = await self.repository.execute_query(base_query, limit)
            
            # Enrich results with additional data
            enriched_results = await self._enrich_search_results(results)
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Error in _search_with_rate_limit: {str(e)}")
            raise
            
    def _apply_search_filters(self, query: Any, filters: DealSearchFilters) -> Any:
        """Apply search filters to the base query."""
        if filters.min_price is not None:
            query = query.filter(Deal.price >= filters.min_price)
        if filters.max_price is not None:
            query = query.filter(Deal.price <= filters.max_price)
        if filters.categories:
            query = query.filter(Deal.category.in_(filters.categories))
        if filters.brands:
            query = query.filter(Deal.brand.in_(filters.brands))
        if filters.condition:
            query = query.filter(Deal.condition.in_(filters.condition))
        if filters.sort_by:
            query = self._apply_sorting(query, filters.sort_by)
        return query
        
    def _apply_sorting(self, query: Any, sort_by: str) -> Any:
        """Apply sorting to the query based on sort parameter."""
        sort_map = {
            "price_asc": Deal.price.asc(),
            "price_desc": Deal.price.desc(),
            "rating": Deal.rating.desc(),
            "expiry": Deal.expires_at.asc(),
            "relevance": Deal.score.desc()
        }
        return query.order_by(sort_map[sort_by])
        
    async def _enrich_search_results(self, results: List[Deal]) -> List[Deal]:
        """Enrich search results with additional data."""
        enriched_results = []
        for deal in results:
            # Add price history
            deal.price_history = await self._get_price_history(deal.id)
            # Add market analysis
            deal.market_analysis = await self._get_market_analysis(deal)
            enriched_results.append(deal)
        return enriched_results
        
    async def _get_price_history(self, deal_id: UUID) -> List[Dict]:
        """Get price history for a deal with caching."""
        cache_key = f"price_history:{deal_id}"
        cached_history = await self.redis.get(cache_key)
        
        if cached_history:
            return json.loads(cached_history)
            
        history = await self.repository.get_price_history(deal_id)
        await self.redis.setex(
            cache_key,
            CACHE_TTL_PRICE_HISTORY,
            json.dumps(history)
        )
        return history
        
    async def _get_market_analysis(self, deal: Deal) -> Dict:
        """Get market analysis for a deal."""
        return {
            "average_market_price": await self._get_average_market_price(deal),
            "price_trend": self._calculate_price_trend(deal.price_history),
            "deal_score": await self._calculate_deal_score(deal)
        }

    def _cache_search(self, query: str, results: List[Deal]) -> None:
        """Cache search results with extended information"""
        try:
            cache_data = {
                'results': [r.json() for r in results],
                'scores': [r.score for r in results],
                'timestamp': datetime.now().isoformat()
            }
            self.redis.set(f"search:{query}", cache_data, ex=600)  # Cache for 10 minutes
        except Exception as e:
            logger.error(f"Failed to cache search results: {str(e)}")

    def _get_cached_search(self, query: str) -> Optional[List[Deal]]:
        """Get cached search results with extended information"""
        try:
            cached_data = self.redis.get(f"search:{query}")
            if cached_data:
                data = json.loads(cached_data)
                return [Deal.parse_raw(r) for r in data['results']]
            return None
        except Exception as e:
            logger.error(f"Failed to get cached search results: {str(e)}")
            return None

    async def get_deals(
        self,
        user_id: UUID,
        filters: DealFilter
    ) -> List[Deal]:
        """Get deals matching the specified criteria.
        
        Args:
            user_id: ID of the user requesting deals
            filters: Deal filter criteria
            
        Returns:
            List[Deal]: List of matching deals
        """
        try:
            # Get deals from repository
            deals = await self.repository.get_deals(user_id, filters)
            
            # Return deals immediately - background processing will be handled by the router
            return deals
            
        except Exception as e:
            logger.error(f"Failed to get deals: {str(e)}")
            raise DealError(f"Failed to get deals: {str(e)}")
            
    async def process_deal_background(self, deal_id: UUID) -> None:
        """Process a deal in the background.
        
        Args:
            deal_id: ID of the deal to process
        """
        try:
            deal = await self.repository.get_by_id(deal_id)
            if not deal:
                logger.error(f"Deal {deal_id} not found for background processing")
                return
                
            # Calculate score and update deal
            score = await self._calculate_deal_score(deal)
            await self.repository.update(deal_id, {"score": score})
            
        except Exception as e:
            logger.error(f"Failed to process deal {deal_id} in background: {str(e)}")
            # Don't raise the error since this is a background task

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True
