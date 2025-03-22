"""AI service for analyzing deals and generating recommendations."""

import os
import re
import json
import logging
import asyncio
import time
import uuid
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Union, Callable
import traceback
import threading
from enum import Enum
from pydantic import BaseModel
import tiktoken
import openai
from openai import AsyncOpenAI, OpenAI
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.config import settings
from core.models.enums import DealSource, MarketType, AIModelType, MarketCategory
from core.models.deal import Deal
from core.utils.logger import get_logger
from core.exceptions import AIServiceError, ConfigurationError, ValidationError
from core.utils.llm import get_llm_instance

# Configure module-level logger
logger = get_logger(__name__)

from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.prompts import PromptTemplate, FewShotPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnablePassthrough
# Import text handling components
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Try to import LLM models
try:
    from langchain_openai import ChatOpenAI as OpenAILLM
except ImportError:
    logger.warning("OpenAI LLM not available - AI functionality will be limited")
    OpenAILLM = None

try:
    # Try to import DeepSeek if available - note the correct class name might be different
    try:
        from langchain_deepseek import ChatDeepSeek as DeepSeekLLM
        logger.info("Successfully imported DeepSeek from langchain_deepseek")
    except ImportError:
        from langchain_community.chat_models import ChatDeepSeek as DeepSeekLLM
        logger.info("Successfully imported DeepSeek from langchain_community")
except ImportError:
    logger.warning("DeepSeek LLM not available - AI functionality will be limited")
    DeepSeekLLM = None

# Global variables for singleton pattern
_ai_service_instance = None
_ai_service_lock = threading.RLock()
_initialization_in_progress = False  # Flag to prevent recursive initialization

class AsyncLock:
    """
    Async wrapper around threading.RLock to support async context manager protocol.
    This allows using the lock in async functions with 'async with' syntax.
    """
    def __init__(self, lock=None):
        """Initialize with an optional existing lock or create a new one."""
        self._lock = lock or threading.RLock()
        
    async def __aenter__(self):
        """Acquire the lock asynchronously."""
        self._lock.acquire()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release the lock asynchronously."""
        self._lock.release()
        
    def acquire(self):
        """Acquire the lock synchronously."""
        return self._lock.acquire()
        
    def release(self):
        """Release the lock synchronously."""
        return self._lock.release()

# Create async-compatible lock from the threading lock
_async_ai_service_lock = AsyncLock(_ai_service_lock)

class AIService:
    """
    Service for AI-related operations such as text generation, analysis, and other LLM tasks.
    This is implemented as a thread-safe singleton to ensure one LLM instance.
    """
    def __new__(cls):
        """
        Implement the singleton pattern to ensure only one instance exists.
        Using the global _ai_service_instance instead of a class-level variable.
        """
        global _ai_service_instance
        with _ai_service_lock:
            if _ai_service_instance is None:
                logger.debug("Creating new AIService instance")
                _ai_service_instance = super(AIService, cls).__new__(cls)
                # Set _initialized to False initially to track initialization state
                _ai_service_instance._initialized = False
            return _ai_service_instance
    
    def __init__(self):
        """
        Initialize the AI service.
        This will be called only once for the singleton instance.
        """
        # Skip initialization if already initialized
        if getattr(self, '_initialized', False):
            return
            
        with _ai_service_lock:
            # Double-check inside the lock
            if getattr(self, '_initialized', False):
                return
                
            try:
                logger.info("Initializing AIService instance")
                
                # Initialize the LLM instance based on available API keys
                self.llm = self._init_llm()
                
                if self.llm is None:
                    logger.warning("No LLM available. AI service will operate in limited mode.")
                
                # Set up other components
                try:
                    # Skip SentenceTransformerEmbeddings as requested by the user
                    logger.info("Skipping embedding model initialization as requested")
                    self.embedding_model = None
                    
                    # Initialize text splitter without requiring external dependencies
                    self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)
                    logger.info("Text splitter initialized successfully")
                except Exception as component_error:
                    logger.warning(f"Error initializing text processing components: {str(component_error)}")
                    logger.warning("Continuing without text processing components")
                    self.embedding_model = None
                    self.text_splitter = None
                
                # Track initialization success - we consider initialization successful even without LLM
                # but with limited functionality
                self._initialized = True
                logger.info(f"AIService initialized successfully. LLM available: {self.llm is not None}")
            except Exception as e:
                # Log error and set initialized flag to False to allow retry
                error_traceback = traceback.format_exc()
                logger.error(f"Failed to initialize AIService: {str(e)}")
                logger.error(f"Exception traceback: {error_traceback}")
                self._initialized = False
    
    def _init_llm(self) -> Optional[BaseLanguageModel]:
        """
        Initialize the LLM based on available API keys.
        
        Returns:
            BaseLanguageModel: An instance of a language model or None if no LLM is available
        """
        try:
            # First try DeepSeek if API key is available
            deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
            if deepseek_api_key and DeepSeekLLM is not None:
                logger.info("Initializing DeepSeek LLM")
                # Add the model parameter which is required
                return DeepSeekLLM(
                    api_key=deepseek_api_key,
                    model="deepseek-chat"  # Add required model parameter
                )
            
            # Fall back to OpenAI if API key is available
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if openai_api_key and OpenAILLM is not None:
                logger.info("Initializing OpenAI LLM")
                return OpenAILLM(
                    api_key=openai_api_key,
                    model="gpt-3.5-turbo"  # Explicitly specify model for consistency
                )
            
            # If no API keys or models, return None
            logger.warning("No LLM API keys or model implementations found. AI functions will be disabled.")
            return None
        except Exception as e:
            logger.error(f"Error initializing LLM: {str(e)}")
            logger.error(traceback.format_exc())
            # Return None to indicate failure
            return None
    
    @property
    def is_initialized(self) -> bool:
        """
        Check if the service is properly initialized.
        
        Returns:
            bool: True if initialized, False otherwise
        """
        return getattr(self, '_initialized', False) and hasattr(self, 'llm')

    async def analyze_deal(self, deal: Deal, no_token_consumption: bool = False) -> Optional[Dict[str, Any]]:
        """
        Analyze a deal using AI to provide insights and recommendations
        
        Args:
            deal: The deal to analyze
            no_token_consumption: If True, the analysis won't consume user tokens
            
        Returns:
            Dictionary containing AI analysis data or a basic fallback analysis
        """
        try:
            # Add more detailed logging
            logger.info(f"------------------- STARTING AI ANALYSIS -------------------")
            logger.info(f"Starting AI analysis for deal {deal.id}, token consumption: {'disabled' if no_token_consumption else 'enabled'}")
            logger.info(f"Deal title: {deal.title}")
            logger.info(f"Deal description available: {bool(deal.description)}")
            if deal.description:
                logger.info(f"Description length: {len(deal.description)}")
                logger.info(f"Description preview: {deal.description[:100]}...")
            logger.info(f"Deal price: {deal.price}, original price: {deal.original_price}")
            
            # Check if LLM is available
            if not self.llm:
                logger.warning("No LLM instance available for analysis - skipping AI analysis")
                return self._generate_basic_analysis(deal)
            
            # Get price history and market data
            price_history = []
            price_points = []
            
            # Extract price points if available - avoid lazy loading
            # Instead of checking hasattr which triggers lazy loading, check if the attribute is already loaded
            # by checking the __dict__ directly to avoid SQLAlchemy lazy loading
            if hasattr(deal, '__dict__') and 'price_points' in deal.__dict__ and isinstance(deal.__dict__['price_points'], list):
                price_points = sorted(
                    [(point.price, point.timestamp) for point in deal.__dict__['price_points']],
                    key=lambda x: x[1] if x[1] else datetime.utcnow()
                )
                logger.info(f"Found {len(price_points)} price points for deal {deal.id}")
            
            # Extract price histories if available - avoid lazy loading in the same way
            if hasattr(deal, '__dict__') and 'price_histories' in deal.__dict__ and isinstance(deal.__dict__['price_histories'], list):
                price_history = sorted(
                    [(point.price, point.created_at) for point in deal.__dict__['price_histories']],
                    key=lambda x: x[1]
                )
                logger.info(f"Found {len(price_history)} price history points for deal {deal.id}")
            
            # Use either price_points or price_history, whichever has more data
            price_data = price_points if len(price_points) > len(price_history) else price_history
            logger.info(f"Using {len(price_data)} price data points for analysis")
            
            # Calculate original price discount if available
            discount_percentage = 0
            if deal.original_price and deal.price:
                discount_percentage = ((deal.original_price - deal.price) / deal.original_price) * 100
                logger.info(f"Calculated discount: {discount_percentage:.2f}% (Original: {deal.original_price}, Current: {deal.price})")
            else:
                logger.info(f"No discount calculation possible - using 0% (Original price missing or invalid)")
            
            # Calculate basic score based on discount
            base_score = min(0.95, max(0.5, discount_percentage / 100 + 0.5))
            logger.info(f"Base score calculated: {base_score:.2f}")
            
            # Determine price trend based on historical data
            price_trend = "unknown"
            price_trend_details = {}
            
            if len(price_data) >= 2:
                # Calculate average rate of change
                start_price = float(price_data[0][0])
                end_price = float(price_data[-1][0])
                days_diff = (price_data[-1][1] - price_data[0][1]).days or 1
                
                if days_diff > 0:
                    daily_change_pct = ((end_price - start_price) / start_price) / days_diff * 100
                    
                    if daily_change_pct < -0.5:
                        price_trend = "falling"
                        # Increase score for falling prices
                        base_score = min(0.98, base_score + 0.1)
                    elif daily_change_pct > 0.5:
                        price_trend = "rising"
                        # Decrease score for rising prices
                        base_score = max(0.3, base_score - 0.1)
                    else:
                        price_trend = "stable"
                    
                    price_trend_details = {
                        "daily_change_percent": daily_change_pct,
                        "start_price": start_price,
                        "end_price": end_price,
                        "days_analyzed": days_diff
                    }
                    
                    logger.info(f"Price trend analysis: {price_trend} with {daily_change_pct:.2f}% daily change")
            
            # Determine confidence based on data quality
            confidence = 0.7  # Default confidence
            
            # Adjust confidence based on available data
            if len(price_data) > 5:
                confidence = 0.9
            elif len(price_data) > 2:
                confidence = 0.8
            elif deal.original_price:
                confidence = 0.75
            else:
                confidence = 0.6
                
            logger.info(f"Confidence level set to {confidence:.2f}")
            
            # Initialize recommendations and additional_market_analysis here, before LLM call
            recommendations = []
            additional_market_analysis = {}
            
            # Skip expensive LLM analysis for very low-value products
            # This is a quick optimization to avoid timeout on low-value items
            if float(deal.price) < 10.0 and not getattr(settings, "ALWAYS_USE_LLM", False):
                logger.info(f"Skipping LLM analysis for low-value product (${float(deal.price):.2f})")
                
                # Generate a simple analysis for low-value products
                simple_score = 0.5 + (discount_percentage / 200)  # Higher discount gives higher score
                simple_score = max(0.1, min(0.9, simple_score))  # Keep between 0.1 and 0.9
                
                return {
                    "score": simple_score,
                    "value": "average",
                    "recommendations": [
                        f"Consider if this ${float(deal.price):.2f} item is worth the purchase given its low price",
                        f"Low-priced items often provide less long-term value; check alternatives"
                    ],
                    "analysis": f"This is a low-priced item at ${float(deal.price):.2f} with a {discount_percentage:.0f}% discount. Simple automated analysis provided due to low price point.",
                    "price_trend": price_trend,
                    "generated_at": datetime.utcnow().isoformat(),
                    "confidence": confidence
                }
            
            # Attempt to use LLM for enhanced analysis if integration is complete
            try:
                if self.llm:
                    # Always use LLM, even for unauthorized users
                    logger.info(f"Using LLM for deal analysis, token consumption tracking: {'disabled' if no_token_consumption else 'enabled'}")
                    
                    # Prepare prompt for LLM
                    product_info = {
                        "title": deal.title,
                        "description": deal.description or "No description available",
                        "price": float(deal.price),
                        "original_price": float(deal.original_price) if deal.original_price else None,
                        "discount_percentage": discount_percentage,
                        "category": str(deal.category) if hasattr(deal, 'category') else "unknown",
                        "price_trend": price_trend,
                        "confidence": confidence
                    }
                    
                    # Log description info specifically for debugging
                    logger.info(f"Using description for LLM prompt: {bool(deal.description)}")
                    if deal.description:
                        logger.info(f"Description length for prompt: {len(deal.description)}")
                        logger.info(f"Description preview for prompt: {deal.description[:100]}...")
                    else:
                        logger.warning("No real description available for LLM prompt, using fallback text")
                    
                    logger.info(f"Prepared product info for LLM: {json.dumps(product_info)}")
                    
                    # Create a prompt for the LLM to analyze the deal
                    prompt = f"""
                    You are an AI assistant specialized in analyzing e-commerce deals.
                    Analyze this product and provide your expert opinion:
                    
                    Product: {product_info['title']}
                    Description: {product_info['description']}
                    Price: ${product_info['price']}
                    Original Price: ${product_info['original_price'] if product_info['original_price'] else 'Unknown'}
                    Discount: {product_info['discount_percentage']}%
                    Category: {product_info['category']}
                    Price Trend: {product_info['price_trend']}
                    
                    Provide exactly two recommendations:
                    1. A clear recommendation on whether to buy or not buy this product with specific reasoning related to the product's features, value, and price.
                    2. A specific insight about this product that would be helpful for someone considering the purchase (e.g., a feature worth noting, a comparison to alternatives, or usage advice).
                    
                    Your recommendations should be:
                    - Directly reference specific details from the product description 
                    - Highlight important features or specifications mentioned in the description
                    - Tailored specifically to this exact product - no generic templates
                    - Insightful and provide unique, valuable information a shopper would appreciate
                    - Written conversationally as if you're advising a friend
                    - Between 1-2 sentences each, concise but informative
                    
                    Also provide:
                    - A score between 0 and 1 (where 1 is an excellent deal)
                    - A brief analysis of the overall value
                    
                    Format your response as JSON:
                    {{
                      "score": 0.X,
                      "recommendations": [
                        "Buy/not buy recommendation with reason based on specific product features",
                        "Product-specific insight that references actual description details"
                      ],
                      "analysis": "brief analysis..."
                    }}
                    """
                    
                    # Call the LLM with the prompt
                    logger.info(f"Sending prompt to LLM for deal {deal.id}")
                    try:
                        # Log LLM details before invocation
                        logger.info(f"LLM type: {type(self.llm).__name__}")
                        if hasattr(self.llm, 'ainvoke') and callable(self.llm.ainvoke):
                            logger.info("LLM has ainvoke method")
                        else:
                            logger.error("LLM does not have ainvoke method!")
                            
                        # Invoke the LLM with a timeout
                        logger.info("Calling LLM.ainvoke() with timeout...")
                        try:
                            # Set a timeout of 20 seconds for the LLM call (increased from 7 seconds)
                            # to accommodate more complex analysis tasks
                            llm_task = asyncio.create_task(self._invoke(prompt))
                            llm_response = await llm_task
                            logger.info(f"LLM response received for deal {deal.id}")
                        except asyncio.TimeoutError:
                            logger.warning(f"LLM call timed out for deal {deal.id}, using fallback analysis")
                            return self._generate_fallback_analysis(deal, "LLM response timed out")

                        try:
                            # Parse the response
                            if isinstance(llm_response, str):
                                response_text = llm_response
                            else:
                                # Assuming it's an object with a content attribute
                                response_text = llm_response.content
                                
                            logger.info(f"Raw LLM response text: {response_text[:200]}...")
                            
                            # Extract the JSON from the response
                            # First try to parse as-is
                            try:
                                analysis = json.loads(response_text)
                                logger.info("Successfully parsed LLM response as JSON")
                            except json.JSONDecodeError:
                                # Try to extract JSON from markdown code blocks
                                json_matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
                                if json_matches:
                                    response_text = json_matches[0]
                                    logger.info(f"Extracted JSON from code block: {response_text[:200]}...")
                                    analysis = json.loads(response_text)
                                    logger.info("Successfully parsed extracted JSON")
                                else:
                                    # Try to find any JSON-like structure
                                    json_pattern = r"\{[\s\S]*\}"
                                    json_matches = re.findall(json_pattern, response_text)
                                    if json_matches:
                                        response_text = json_matches[0]
                                        logger.info(f"Found JSON-like structure: {response_text[:200]}...")
                                        analysis = json.loads(response_text)
                                        logger.info("Successfully parsed JSON-like structure")
                                    else:
                                        raise ValueError("Could not find JSON in LLM response")
                            
                            # Get recommendations from the analysis
                            if 'recommendations' in analysis and analysis['recommendations']:
                                recommendations = analysis['recommendations']
                                logger.info(f"Retrieved {len(recommendations)} AI-generated recommendations")
                                for i, rec in enumerate(recommendations):
                                    logger.info(f"AI recommendation {i+1}: {rec}")
                            else:
                                logger.warning("No recommendations found in LLM response")
                                # Set fallback recommendations
                                recommendations = [
                                    f"Based on the {discount_percentage:.1f}% discount, this appears to be a reasonable deal if you need {deal.title}.",
                                    f"Compare with similar products in the {str(deal.category)} category to ensure you're getting the best value."
                                ]
                                logger.info("Using basic fallback recommendations")
                            
                            # Get the score from the analysis
                            if 'score' in analysis:
                                try:
                                    # Make sure the score is a float between 0 and 1
                                    base_score = float(analysis['score'])
                                    base_score = max(0.0, min(1.0, base_score))  # Clamp to 0-1
                                    logger.info(f"Using LLM-provided score: {base_score}")
                                except (ValueError, TypeError):
                                    logger.warning(f"Invalid score format in LLM response: {analysis.get('score')}")
                            else:
                                logger.warning("No score found in LLM response, using calculated score")
                        
                        except Exception as parsing_error:
                            logger.error(f"Error parsing LLM response: {str(parsing_error)}")
                            logger.error(f"Raw response: {response_text}")
                            # Use fallback recommendations
                            recommendations = [
                                f"Based on the {discount_percentage:.1f}% discount, this appears to be a reasonable deal if you need {deal.title}.",
                                f"Compare with similar products in the {str(deal.category)} category to ensure you're getting the best value."
                            ]
                            logger.info("Using basic fallback recommendations due to parsing error")
                    except Exception as e:
                        logger.error(f"Error calling LLM: {str(e)}")
            except Exception as e:
                logger.error(f"Error in LLM analysis: {str(e)}")
                logger.error(traceback.format_exc())
            
            # Determine availability
            is_available = True
            availability_status = "Available"
            
            if hasattr(deal, 'status') and deal.status:
                is_available = str(deal.status).lower() in ("active", "available")
                availability_status = "Available" if is_available else "Unavailable"
            
            if hasattr(deal, 'availability') and deal.availability:
                if isinstance(deal.availability, dict) and 'status' in deal.availability:
                    availability_status = deal.availability['status']
                    
            # Get market information
            market_info = {}
            if hasattr(deal, '__dict__') and 'market' in deal.__dict__ and deal.__dict__['market'] is not None:
                market = deal.__dict__['market']
                market_name = market.name if hasattr(market, 'name') else "Unknown Market"
                market_type = market.type if hasattr(market, 'type') else "Unknown"
                market_info = {
                    "name": market_name,
                    "type": market_type
                }
                logger.info(f"Found market info: {market_name} ({market_type})")
            
            # Extract data from metadata if available
            if hasattr(deal, 'deal_metadata') and deal.deal_metadata:
                if isinstance(deal.deal_metadata, dict):
                    logger.info(f"Using deal_metadata for additional analysis")
                    if 'market_analysis' in deal.deal_metadata:
                        additional_market_analysis = deal.deal_metadata['market_analysis']
                    if 'popularity' in deal.deal_metadata:
                        additional_market_analysis['popularity'] = deal.deal_metadata['popularity']
                    if 'competition' in deal.deal_metadata:
                        additional_market_analysis['competition'] = deal.deal_metadata['competition']
            
            # Create analysis dictionary in the format expected by _convert_to_response
            analysis = {
                "deal_id": str(deal.id),
                "score": base_score,
                "confidence": confidence,
                "price_analysis": {
                    "discount_percentage": float(discount_percentage),
                    "is_good_deal": base_score > 0.7,
                    "price_trend": price_trend,
                    "trend_details": price_trend_details,
                    "original_price": float(deal.original_price) if deal.original_price else None,
                    "current_price": float(deal.price)
                },
                "market_analysis": {
                    "competition": additional_market_analysis.get('competition', "Average"),
                    "availability": availability_status,
                    "market_info": market_info,
                    "price_position": additional_market_analysis.get('price_position', "Mid-range"),
                    "popularity": additional_market_analysis.get('popularity', "Unknown")
                },
                "recommendations": recommendations,
                "analysis_date": datetime.utcnow().isoformat(),
                "expiration_analysis": "Deal expires on " + deal.expires_at.isoformat() if deal.expires_at else "No expiration date available"
            }
            
            logger.info(f"Completed AI analysis for deal {deal.id} with score {base_score:.2f}")
            logger.debug(f"Analysis result: {json.dumps(analysis)}")
            
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing deal {deal.id if deal else 'Unknown'}: {str(e)}")
            logger.error(traceback.format_exc())
            return self._generate_fallback_analysis(deal, str(e))
            
    def _generate_fallback_analysis(self, deal: Deal, error_message: str) -> Dict[str, Any]:
        """Generate a fallback analysis when normal analysis fails"""
        logger.warning(f"Generating fallback analysis for deal {deal.id}: {error_message}")
        
        # Calculate basic discount if possible
        discount_percentage = 0
        if deal and deal.original_price and deal.price:
            try:
                discount_percentage = ((deal.original_price - deal.price) / deal.original_price) * 100
                logger.info(f"Fallback analysis calculated discount: {discount_percentage:.2f}%")
            except Exception as e:
                logger.error(f"Error calculating discount in fallback: {str(e)}")
        
        # Extract product name and details for more natural recommendations
        product_name = "this product"
        if deal and deal.title:
            # Get first 2-4 words of title as product name
            title_words = deal.title.split(" ")
            product_name = " ".join(title_words[:min(4, len(title_words))])
        
        # Use description if available
        product_description = None
        if deal and deal.description and len(deal.description) > 20:
            product_description = deal.description
            logger.info(f"Using product description for fallback analysis: {product_description[:100]}...")
        
        # Create meaningful fallback recommendations
        recommendations = []
        
        # Buy/Not Buy recommendation based on discount
        if discount_percentage > 30:
            recommendations.append(f"At {discount_percentage:.1f}% off, this is an excellent time to buy {product_name}. The significant discount makes it a great value purchase compared to its regular price.")
        elif discount_percentage > 15:
            recommendations.append(f"With a {discount_percentage:.1f}% discount, {product_name} offers good value. If you've been considering this purchase, now is a reasonable time to buy.")
        elif discount_percentage > 5:
            recommendations.append(f"The current {discount_percentage:.1f}% discount on {product_name} is modest. Unless you need it urgently, you might want to wait for a better deal.")
        else:
            recommendations.append(f"There's minimal discount ({discount_percentage:.1f}%) on {product_name} right now. I'd recommend waiting for a price drop before purchasing.")
        
        # General product recommendation using description if available
        if product_description:
            # Extract key features or aspects from description
            desc_lower = product_description.lower()
            
            # Check for common feature indicators
            if any(term in desc_lower for term in ["waterproof", "water resistant", "water-resistant"]):
                recommendations.append(f"This {product_name} features water resistance, making it suitable for outdoor use or wet conditions. Consider this advantage when comparing with alternatives.")
            elif any(term in desc_lower for term in ["wireless", "bluetooth", "wifi", "wi-fi"]):
                recommendations.append(f"The wireless functionality of this {product_name} adds convenience but verify the connectivity range and battery life for your specific needs.")
            elif any(term in desc_lower for term in ["battery", "rechargeable", "charge"]):
                recommendations.append(f"Pay attention to the battery performance of this {product_name} - check user reviews specifically about battery life and charging speed.")
            elif "warranty" in desc_lower:
                recommendations.append(f"This {product_name} comes with a warranty, which adds value to your purchase. Check the warranty terms and what's covered before buying.")
            else:
                # Use category-based recommendation as fallback
                category = deal.category if deal and hasattr(deal, 'category') else None
                category_str = str(category).lower() if category else ""
                
                if "electronics" in category_str:
                    recommendations.append(f"For electronics like this {product_name}, verify compatibility with your existing devices and check user reviews about reliability and customer support.")
                elif any(term in category_str for term in ["clothing", "apparel", "fashion"]):
                    recommendations.append(f"When purchasing clothing items like this {product_name}, carefully review the sizing information and material composition to ensure it meets your expectations.")
                elif any(term in category_str for term in ["home", "kitchen", "furniture"]):
                    recommendations.append(f"For home items like this {product_name}, confirm the dimensions to ensure it fits your space, and check customer reviews for quality and durability insights.")
                else:
                    recommendations.append(f"Research this {product_name} thoroughly, focusing on reviews from verified purchasers that address quality and value for the price.")
        else:
            # Category-based recommendation without description
            category = deal.category if deal and hasattr(deal, 'category') else None
            if category:
                category_str = str(category).lower()
                if "electronics" in category_str:
                    recommendations.append(f"For electronics like {product_name}, always check warranty terms and read reviews about reliability and longevity.")
                elif "clothing" in category_str or "apparel" in category_str:
                    recommendations.append(f"When buying clothing online, especially items like {product_name}, verify the size chart and check return policies.")
                else:
                    recommendations.append(f"Take time to compare {product_name} with similar products to ensure you're getting the features you need at the best price.")
            else:
                recommendations.append(f"Research {product_name} thoroughly before purchasing - read customer reviews focusing on quality and value for money.")
        
        # Ensure we have exactly two recommendations
        if len(recommendations) > 2:
            recommendations = recommendations[:2]
        elif len(recommendations) < 2:
            recommendations.append(f"Consider your specific needs when evaluating {product_name} - determine if its features align with what you'll actually use.")
        
        # Get market information
        market_info = {
            "name": deal.source.capitalize() if (deal and deal.source) else "Unknown Market",
            "type": deal.source.lower() if (deal and deal.source) else "unknown"
        }
        
        # Return simplified analysis
        return {
            "deal_id": str(deal.id) if deal else "unknown",
            "score": 0.5,
            "confidence": 0.3,
            "price_analysis": {
                "discount_percentage": float(discount_percentage),
                "is_good_deal": discount_percentage > 20,
                "price_trend": "unknown",
                "trend_details": {},
                "original_price": float(deal.original_price) if deal and deal.original_price else None,
                "current_price": float(deal.price) if deal and deal.price else 0.0
            },
            "market_analysis": {
                "competition": "Average",
                "availability": "Unknown",
                "market_info": market_info,
                "price_position": "Mid-range",
                "popularity": "Unknown"
            },
            "recommendations": recommendations,
            "analysis_date": datetime.utcnow().isoformat(),
            "expiration_analysis": "Deal expires on " + deal.expires_at.isoformat() if (deal and deal.expires_at) else "No expiration date available"
        }
        
    async def test_llm_connection(self) -> Dict[str, Any]:
        """
        Test the LLM connection and return detailed diagnostics
        
        Returns:
            Dictionary with test results and diagnostic information
        """
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "llm_instance_exists": self.llm is not None,
            "llm_type": str(type(self.llm).__name__) if self.llm else "None",
            "environment_variables": {
                "deepseek_key_exists": bool(os.environ.get("DEEPSEEK_API_KEY")),
                "openai_key_exists": bool(os.environ.get("OPENAI_API_KEY")),
            },
            "connection_test": None,
            "available_models": []
        }
        
        # Test connection only if LLM is available
        if self.llm is None:
            results["connection_test"] = {
                "success": False,
                "error": "No LLM instance available"
            }
            return results
        
        # Test connection
        try:
            # Simple test prompt
            test_prompt = "Say 'Connection successful' if you can read this message."
            
            # Invoke the model
            response = await self._invoke(test_prompt)
            
            results["connection_test"] = {
                "success": True,
                "error": None
            }
        except Exception as e:
            results["connection_test"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"Error testing LLM connection: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Log LLM details if available
        if self.llm:
            model_info = {}
            
            # Extract model name if available
            if hasattr(self.llm, "model_name"):
                model_info["model_name"] = self.llm.model_name
            elif hasattr(self.llm, "model"):
                model_info["model_name"] = self.llm.model
                
            # Extract provider if available
            if hasattr(self.llm, "provider"):
                model_info["provider"] = self.llm.provider
            elif "deepseek" in str(type(self.llm)).lower():
                model_info["provider"] = "deepseek"
            elif "openai" in str(type(self.llm)).lower():
                model_info["provider"] = "openai"
            else:
                model_info["provider"] = "unknown"
                
            # Extract other attributes
            for attr in ["temperature", "max_tokens", "api_key"]:
                if hasattr(self.llm, attr):
                    value = getattr(self.llm, attr)
                    # Mask API keys for security
                    if attr == "api_key" and value:
                        # Ensure value is a string before slicing
                        str_value = str(value)
                        value = f"{str_value[:4]}...{str_value[-4:]}" if len(str_value) > 8 else "***"
                    model_info[attr] = value
            
            results["model_info"] = model_info
        
        # Try to list available models if we can import the modules
        try:
            # Try DeepSeek
            if os.environ.get("DEEPSEEK_API_KEY") and DeepSeekLLM is not None:
                results["available_models"].append({"provider": "deepseek", "models": ["deepseek-chat"]})
            
            # Try OpenAI
            if os.environ.get("OPENAI_API_KEY") and OpenAILLM is not None:
                # List OpenAI models
                results["available_models"].append({"provider": "openai", "models": ["gpt-3.5-turbo", "gpt-4o"]})
        except Exception as e:
            logger.error(f"Error listing available models: {str(e)}")
            
        return results 

    async def _invoke(self, prompt):
        """Internal method to invoke the LLM with proper error handling.
        
        Args:
            prompt: The prompt to send
            
        Returns:
            LLM response
        """
        try:
            # This line is causing the issue - the invoke method might not return an awaitable object
            # return await self.llm.invoke(prompt)
            
            # Fixed implementation - use the appropriate async method
            if hasattr(self.llm, 'ainvoke') and callable(self.llm.ainvoke):
                # Use async invoke if available
                return await self.llm.ainvoke(prompt)
            elif hasattr(self.llm, 'async_invoke') and callable(self.llm.async_invoke):
                # Alternative async method name
                return await self.llm.async_invoke(prompt)
            else:
                # If no async method is available, use a synchronous call but wrapped
                # in a thread to avoid blocking
                from concurrent.futures import ThreadPoolExecutor
                
                with ThreadPoolExecutor() as executor:
                    response = await asyncio.get_event_loop().run_in_executor(
                        executor, self.llm.invoke, prompt
                    )
                return response
        except Exception as e:
            logger.error(f"Error in LLM invoke: {str(e)}")
            raise

    async def analyze_search_query(self, query: str, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a search query using the LLM to extract structured search parameters.
        
        Args:
            query: The search query to analyze
            category: Optional category to help focus the analysis
            
        Returns:
            Dict containing extracted search parameters
        """
        logger.info(f"Analyzing search query: {query}")
        
        # If no LLM is available, return a basic fallback analysis
        if not self.llm:
            logger.warning("LLM not available for query analysis, using basic extraction")
            return self._generate_basic_query_analysis(query)
        
        try:
            # Create a category hint if category is provided
            category_hint = f" Focus on the {category} category." if category else ""
            
            # Create the prompt for the LLM
            system_prompt = (
                "You are a helpful assistant that extracts structured search parameters from a user's shopping query. "
                "Extract the following information as JSON:\n"
                "- keywords: Main search terms (required)\n"
                "- category: Product category (required) - IMPORTANT: You must ONLY use one of the following categories:\n"
                "  * 'electronics' - for electronic devices, computers, phones, gadgets\n"
                "  * 'fashion' - for clothing, shoes, accessories, jewelry\n" 
                "  * 'home' - for furniture, decor, kitchen items, household goods\n"
                "  * 'toys' - for children's toys, games, puzzles\n"
                "  * 'books' - for books, e-books, textbooks, literature\n"
                "  * 'sports' - for sports equipment, fitness gear, outdoor activities\n"
                "  * 'automotive' - for car parts, accessories, maintenance items\n"
                "  * 'health' - for health supplements, medical devices, wellness products\n"
                "  * 'beauty' - for cosmetics, skincare, personal care\n"
                "  * 'grocery' - for food, beverages, pantry items\n"
                "  * 'other' - ONLY if the product doesn't fit in any of the above\n"
                "- min_price: Minimum price (if mentioned)\n"
                "- max_price: Maximum price (if mentioned)\n"
                "- brands: Array of mentioned brands (if any)\n"
                "- features: Array of desired features (if any)\n"
                "- quality: Quality level/requirements (if any)\n"
                "Use null for missing fields. Only extract what is explicitly or strongly implied in the query.\n"
                "For the category field, you MUST select the most appropriate category from the list above. "
                "If uncertain, choose the closest matching category. If nothing matches, use 'other'."
                f"{category_hint}"
            )
            
            # Call the LLM
            response = await self.llm.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.2,  # Lower temperature for deterministic responses
                max_tokens=250    # Reduced max tokens for faster responses
            )
            
            # Extract the content from the response
            if hasattr(response, 'content'):
                llm_response = response.content
            elif isinstance(response, dict) and 'content' in response:
                llm_response = response['content']
            else:
                llm_response = str(response)
            
            # Parse the JSON
            import json
            import re
            
            # Try to extract JSON from the response
            json_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', llm_response)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no markdown code block, try to find JSON directly
                json_match = re.search(r'({[\s\S]*})', llm_response)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # If still no match, use the whole response
                    json_str = llm_response
            
            # Parse JSON
            parsed_data = json.loads(json_str)
            
            # Validate required fields
            if 'keywords' not in parsed_data or not parsed_data['keywords']:
                parsed_data['keywords'] = query
                
            if 'category' not in parsed_data or not parsed_data['category']:
                parsed_data['category'] = category or 'other'
            
            # Additional validation for category to ensure it's one of our valid enum values
            from core.models.enums import MarketCategory
            valid_categories = [cat.value.lower() for cat in MarketCategory]
            
            if parsed_data['category'].lower() not in valid_categories:
                logger.warning(f"AI returned invalid category: {parsed_data['category']}. Defaulting to 'other'")
                parsed_data['category'] = 'other'
            
            # Return the parsed data
            return parsed_data
                
        except Exception as e:
            logger.error(f"Error analyzing query with LLM: {str(e)}")
            return self._generate_basic_query_analysis(query)

    def _generate_basic_query_analysis(self, query: str) -> Dict[str, Any]:
        """
        Generate a basic search query analysis when LLM is not available.
        
        Args:
            query: The search query to analyze
            
        Returns:
            Dict containing extracted parameters
        """
        # Normalize the query
        normalized_query = query.lower()
        
        # Extract price ranges
        min_price = None
        max_price = None
        
        # Check for price patterns like "under $50" or "$20-$30"
        price_under_match = re.search(r'under\s+\$?(\d+)', normalized_query)
        price_range_match = re.search(r'\$?(\d+)\s*-\s*\$?(\d+)', normalized_query)
        price_above_match = re.search(r'over\s+\$?(\d+)', normalized_query)
        
        if price_under_match:
            max_price = float(price_under_match.group(1))
        elif price_range_match:
            min_price = float(price_range_match.group(1))
            max_price = float(price_range_match.group(2))
        elif price_above_match:
            min_price = float(price_above_match.group(1))
        
        # Guess the category based on common product types in the query
        from core.models.enums import MarketCategory
        
        # Get all valid categories from the enum
        valid_categories = [cat.value.lower() for cat in MarketCategory]
        
        # Default category
        category = 'other'
        
        # Map of keywords to categories
        category_keywords = {
            'electronics': ['phone', 'laptop', 'computer', 'tablet', 'headphone', 'earbud', 'tv', 'speaker', 'camera', 'gaming'],
            'fashion': ['shirt', 'pants', 'dress', 'shoe', 'jacket', 'coat', 'watch', 'jewelry', 'handbag', 'clothing'],
            'home': ['furniture', 'sofa', 'chair', 'table', 'lamp', 'rug', 'cookware', 'kitchen', 'bedding', 'decor'],
            'toys': ['toy', 'game', 'puzzle', 'lego', 'doll', 'action figure', 'board game', 'playset'],
            'books': ['book', 'novel', 'textbook', 'cookbook', 'biography', 'fiction', 'literature'],
            'sports': ['bicycle', 'bike', 'treadmill', 'weight', 'exercise', 'fitness', 'sports', 'outdoor'],
            'automotive': ['car', 'auto', 'vehicle', 'truck', 'motorcycle', 'automotive', 'parts', 'accessory'],
            'health': ['vitamin', 'supplement', 'medicine', 'medical', 'health', 'healthcare'],
            'beauty': ['makeup', 'skincare', 'cosmetic', 'beauty', 'hair', 'lotion', 'fragrance'],
            'grocery': ['food', 'drink', 'grocery', 'snack', 'beverage', 'coffee', 'tea'],
        }
        
        # Find category that has the most keyword matches
        max_matches = 0
        for cat, keywords in category_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in normalized_query)
            if matches > max_matches:
                max_matches = matches
                category = cat
        
        # If no matches found or not a valid category, use 'other'
        if max_matches == 0 or category.lower() not in valid_categories:
            category = 'other'
            
        # Extract potential brands (simplified)
        common_brands = [
            'apple', 'samsung', 'sony', 'lg', 'nike', 'adidas', 'amazon', 'google',
            'microsoft', 'dell', 'hp', 'lenovo', 'asus', 'acer', 'nintendo', 'xbox',
            'playstation', 'dyson', 'kitchenaid', 'cuisinart', 'philips', 'bose'
        ]
        
        brands = []
        for brand in common_brands:
            if brand in normalized_query:
                brands.append(brand)
        
        # Return the basic analysis
        return {
            'keywords': query,
            'category': category,
            'min_price': min_price,
            'max_price': max_price,
            'brands': brands if brands else None,
            'features': None,
            'quality': None
        }

    async def analyze_products(self, products: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Analyze a list of products to add AI-powered insights."""
        if not self.llm:
            logger.warning("No LLM available - skipping product analysis")
            return products
        
        # This is a placeholder for future implementation
        return products
            
    async def analyze_goal(self, goal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a goal using AI to provide structured information and recommendations
        
        Args:
            goal_data: Dictionary containing goal data including title, description, etc.
            
        Returns:
            Dictionary containing analysis, extracted keywords, complexity, and recommended actions
        """
        logger.info(f"Analyzing goal: {goal_data.get('title', 'Untitled')}")
        
        if not self.llm:
            logger.warning("No LLM available - returning basic goal analysis")
            return {
                "analysis": f"Basic analysis of {goal_data.get('title', 'Untitled Goal')} (AI unavailable)", 
                "keywords": goal_data.get("title", "").split()[:5] if goal_data.get("title") else [], 
                "complexity": 0.5, 
                "recommended_actions": ["search", "monitor"]
            }
        
        # Placeholder for actual implementation
        return {
            "analysis": f"Analysis of {goal_data.get('title', 'Untitled Goal')}", 
            "keywords": goal_data.get("title", "").split()[:5] if goal_data.get("title") else [], 
            "complexity": 0.5, 
            "recommended_actions": ["search", "monitor"]
        }

    def _generate_basic_analysis(self, deal: Deal) -> Dict[str, Any]:
        """Generate a basic analysis without AI when LLM is not available"""
        logger.info(f"Generating basic analysis for deal {deal.id} (AI functionality disabled)")
        
        # Calculate basic discount if possible
        discount_percentage = 0
        if deal and deal.original_price and deal.price:
            try:
                discount_percentage = ((deal.original_price - deal.price) / deal.original_price) * 100
                logger.info(f"Basic analysis calculated discount: {discount_percentage:.2f}%")
            except Exception as e:
                logger.error(f"Error calculating discount: {str(e)}")
        
        # Extract product name
        product_name = "this product"
        if deal and deal.title:
            # Get first 2-4 words of title as product name
            title_words = deal.title.split(" ")
            product_name = " ".join(title_words[:min(4, len(title_words))])
        
        # Set a basic value score based on discount
        value_score = 0.5  # Default to average
        if discount_percentage > 30:
            value_score = 0.8  # Good deal
        elif discount_percentage > 15:
            value_score = 0.65  # Above average deal

        # Get market information
        market_info = {
            "name": deal.source.capitalize() if (deal and deal.source) else "Unknown Market",
            "type": deal.source.lower() if (deal and deal.source) else "unknown"
        }
        
        # Return simplified analysis
        return {
            "deal_id": str(deal.id) if deal else "unknown",
            "score": value_score,
            "confidence": 0.3,
            "price_analysis": {
                "discount_percentage": float(discount_percentage),
                "is_good_deal": discount_percentage > 20,
                "price_trend": "unknown",
                "trend_details": {},
                "original_price": float(deal.original_price) if deal and deal.original_price else None,
                "current_price": float(deal.price) if deal and deal.price else 0.0
            },
            "market_analysis": {
                "competition": "Unknown",
                "availability": "Unknown",
                "market_info": market_info,
                "price_position": "Unknown",
                "popularity": "Unknown"
            },
            "recommendations": [
                "AI analysis not available. Basic discount calculation only.",
                f"This product has a {discount_percentage:.1f}% discount from original price."
            ],
            "analysis_date": datetime.utcnow().isoformat(),
            "expiration_analysis": "AI analysis not available."
        }

async def get_ai_service() -> Optional[AIService]:
    """
    Get a singleton instance of the AI service.
    This is the preferred way to access the AIService.
    
    Returns:
        AIService instance or None if initialization fails
    """
    global _ai_service_instance, _initialization_in_progress
    
    # Fast path: Return instance if already initialized
    if _ai_service_instance is not None and getattr(_ai_service_instance, '_initialized', False):
        return _ai_service_instance
    
    # Acquire lock for the initialization process
    async with _async_ai_service_lock:
        # Double-check after acquiring the lock
        if _ai_service_instance is not None and getattr(_ai_service_instance, '_initialized', False):
            return _ai_service_instance
            
        # If initialization is already in progress, wait rather than returning None
        if _initialization_in_progress:
            logger.debug("AIService initialization already in progress, waiting...")
            # Return the current instance (which may be None or partially initialized)
            return _ai_service_instance
            
        # Mark initialization as in progress
        _initialization_in_progress = True
        
        try:
            # Create a new instance (this will reuse the existing instance if one exists)
            # The __new__ method will handle the singleton logic
            instance = AIService()
            
            # Only log if initialization succeeded
            if getattr(instance, '_initialized', False):
                logger.info(f"AIService initialized successfully with LLM: {getattr(instance, 'llm', None)}")
            else:
                logger.error("Failed to initialize AIService (instance reports not initialized)")
            
            return instance
        except Exception as e:
            # Log the error with traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error initializing AIService: {str(e)}")
            logger.error(f"Exception traceback: {error_traceback}")
            
            # Return None to indicate initialization failure
            return None
        finally:
            # Always reset the initialization flag, even if an error occurred
            _initialization_in_progress = False

async def reset_ai_service() -> None:
    """Reset the AIService singleton instance (mainly for testing)."""
    global _ai_service_instance, _async_ai_service_lock
    
    try:
        async with _async_ai_service_lock:
            _ai_service_instance = None
            logger.info("AIService singleton instance has been reset")
    except Exception as e:
        logger.error(f"Error resetting AIService: {str(e)}")
