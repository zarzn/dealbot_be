from typing import Optional, Dict, Any, List
import logging
import json
import os
from decimal import Decimal
from uuid import UUID
from datetime import datetime, timedelta
import traceback
import sys

from core.models.deal import Deal, AIAnalysis
from core.utils.llm import get_llm_instance, LLMProvider, test_llm_connection
from core.config import settings

logger = logging.getLogger(__name__)

class AIService:
    """Service for AI-powered analysis and predictions"""

    def __init__(self):
        """Initialize the AI service."""
        logger.info("Initializing AIService")
        try:
            # Check environment variables for API keys
            deep_seek_key = os.environ.get("DEEPSEEK_API_KEY")
            openai_key = os.environ.get("OPENAI_API_KEY")
            
            logger.info(f"DeepSeek API key available: {deep_seek_key is not None}")
            logger.info(f"OpenAI API key available: {openai_key is not None}")
            
            # Temporarily override TESTING to ensure we don't use MockLLM due to testing mode
            original_testing = getattr(settings, "TESTING", False)
            if hasattr(settings, "TESTING"):
                logger.info(f"Temporarily disabling testing mode for LLM initialization (was {original_testing})")
                settings.TESTING = False
            
            # Get LLM instance with detailed logging
            logger.info("Attempting to initialize LLM instance")
            self.llm = get_llm_instance()
            
            # Restore original testing setting
            if hasattr(settings, "TESTING"):
                logger.info(f"Restoring testing mode to {original_testing}")
                settings.TESTING = original_testing
            
            # Log information about the LLM
            if self.llm:
                if hasattr(self.llm, "model_name"):
                    logger.info(f"LLM initialized with model: {self.llm.model_name}")
                elif hasattr(self.llm, "model"):
                    logger.info(f"LLM initialized with model: {self.llm.model}")
                else:
                    logger.info(f"LLM initialized with type: {type(self.llm).__name__}")
                
                # Log additional model details if available
                logger.info(f"LLM details: {str(self.llm)[:200]}...")
                logger.info("LLM instance initialized successfully")
            else:
                logger.error("LLM instance is None after initialization")
        except Exception as e:
            logger.error(f"Error initializing LLM: {str(e)}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            logger.error(f"Python version: {sys.version}")
            self.llm = None

    async def analyze_deal(self, deal: Deal, no_token_consumption: bool = False) -> Optional[Dict[str, Any]]:
        """
        Analyze a deal using AI to provide insights and recommendations
        
        Args:
            deal: The deal to analyze
            no_token_consumption: If True, the analysis won't consume user tokens
            
        Returns:
            Dictionary containing AI analysis data
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
                logger.error("No LLM instance available for analysis")
                return self._generate_fallback_analysis(deal, "No LLM instance available")
            
            # Get price history and market data
            price_history = []
            price_points = []
            
            # Extract price points if available - avoid lazy loading
            if hasattr(deal, '_sa_instance_state') and hasattr(deal, 'price_points'):
                # Check if price_points is already loaded (not a lazy-loading proxy)
                if 'price_points' in deal.__dict__ and isinstance(deal.__dict__['price_points'], list):
                    price_points = sorted(
                        [(point.price, point.timestamp) for point in deal.__dict__['price_points']],
                        key=lambda x: x[1] if x[1] else datetime.utcnow()
                    )
                    logger.info(f"Found {len(price_points)} price points for deal {deal.id}")
            
            # Extract price histories if available - avoid lazy loading
            if hasattr(deal, '_sa_instance_state') and hasattr(deal, 'price_histories'):
                # Check if price_histories is already loaded (not a lazy-loading proxy)
                if 'price_histories' in deal.__dict__ and isinstance(deal.__dict__['price_histories'], list):
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
                        if hasattr(self.llm, 'invoke'):
                            logger.info("LLM has invoke method")
                        else:
                            logger.error("LLM does not have invoke method!")
                            
                        # Invoke the LLM
                        logger.info("Calling LLM.invoke()...")
                        llm_response = self.llm.invoke(prompt)
                        logger.info(f"LLM response received for deal {deal.id}")
                        
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
                                import re
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
            if hasattr(deal, 'market') and deal.market:
                market_name = deal.market.name if hasattr(deal.market, 'name') else "Unknown Market"
                market_type = deal.market.type if hasattr(deal.market, 'type') else "Unknown"
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
        
        # Test connection
        try:
            connection_success = test_llm_connection()
            results["connection_test"] = {
                "success": connection_success,
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
                        value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
                    model_info[attr] = value
            
            results["model_info"] = model_info
        
        # Try to list available models if we can import the modules
        try:
            # Try DeepSeek
            if os.environ.get("DEEPSEEK_API_KEY"):
                try:
                    import deepseek
                    # List models would be called here if the API supported it
                    results["available_models"].append({"provider": "deepseek", "models": ["deepseek-chat"]})
                except ImportError:
                    logger.warning("DeepSeek module not available")
        except Exception as e:
            logger.error(f"Error listing available models: {str(e)}")
            
        return results 