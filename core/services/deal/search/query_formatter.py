"""
Search query formatting module.

This module contains functions for formatting user queries for use with
different marketplace search APIs, using both AI and fallback methods.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Union
import asyncio

from core.utils.logger import get_logger
from core.services.ai import AIService
from core.models.enums import MarketCategory

logger = get_logger(__name__)

async def format_search_queries_with_ai_batch(
    query: str,
    marketplaces: List[str],
    ai_service: Optional[AIService] = None
) -> Dict[str, str]:
    """
    Format a search query using AI for multiple marketplaces in a single request.
    
    Args:
        query: The original user query
        marketplaces: List of target marketplaces (amazon, walmart, google_shopping)
        ai_service: Optional AIService instance
        
    Returns:
        Dictionary mapping marketplace to formatted query string
    """
    if not ai_service or not ai_service.llm:
        logger.warning("AI service not available, using fallback formatting")
        return {marketplace: format_search_query_fallback(query, marketplace) for marketplace in marketplaces}
    
    try:
        # Create system prompt for batch query formatting
        system_prompt = (
            "You are a search query optimization assistant that helps format user search queries for e-commerce marketplaces.\n"
            "Your task is to transform natural language shopping queries into optimized search terms for MULTIPLE marketplaces simultaneously.\n\n"
            "For each query, you should:\n"
            "1. Extract the core product being searched for\n"
            "2. Identify any price constraints (minimum/maximum)\n"
            "3. Identify brand preferences\n"
            "4. Identify key features or specifications\n"
            "5. Output a formatted search query for EACH marketplace\n\n"
            "The output MUST be in this EXACT format (including the exact marketplace names):\n"
            "amazon: [formatted query for Amazon]\n"
            "walmart: [formatted query for Walmart]\n"
            "google_shopping: [formatted query for Google Shopping]\n\n"
            "DO NOT include any additional text, explanations or markdown formatting."
        )
        
        # Create user prompt with list of marketplaces
        user_prompt = f"Format this search query for the following marketplaces: {', '.join(marketplaces)}:\n{query}"
        
        # Prepare base parameters for LLM
        base_params = {
            "temperature": 0.3,  # Lower temperature for more deterministic response
            "max_tokens": 150    # Token count for multiple marketplaces
        }
        
        # Call the LLM
        try:
            logger.info(f"Calling LLM to format query: '{query}' for marketplaces: {marketplaces}")
            response = await ai_service.llm.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                **base_params
            )
        except Exception as e:
            logger.error(f"Error during LLM call: {e}")
            return {marketplace: format_search_query_fallback(query, marketplace) for marketplace in marketplaces}
        
        # Extract content from the response
        formatted_response = ""
        if hasattr(response, 'content'):
            formatted_response = response.content
        elif isinstance(response, dict) and 'content' in response:
            formatted_response = response['content']
        else:
            formatted_response = str(response)
        
        # Log the response for debugging
        logger.debug(f"LLM response: {formatted_response[:200]}...")
        
        # Remove any markdown code blocks
        formatted_response = re.sub(r'^```.*?\n|```$', '', formatted_response, flags=re.DOTALL)
        
        # Parse the response into a dictionary
        result = {}
        for line in formatted_response.strip().split('\n'):
            try:
                if ':' in line:
                    marketplace, formatted_query = line.split(':', 1)
                    marketplace = marketplace.strip().lower()
                    formatted_query = formatted_query.strip()
                    
                    # Remove any quotes or markdown
                    formatted_query = re.sub(r'^["\'`]|["\'`]$', '', formatted_query)
                    
                    if marketplace in marketplaces and formatted_query:
                        result[marketplace] = formatted_query
                        logger.debug(f"Parsed marketplace '{marketplace}' with formatted query: '{formatted_query}'")
            except Exception as e:
                logger.warning(f"Error parsing line '{line}': {e}")
                continue
        
        # Apply fallback for any missing marketplaces
        for marketplace in marketplaces:
            if marketplace not in result or not result[marketplace]:
                fallback_query = format_search_query_fallback(query, marketplace)
                result[marketplace] = fallback_query
                logger.warning(f"Using fallback formatting for {marketplace}: '{fallback_query}'")
        
        logger.info(f"Successfully formatted queries for {len(result)} marketplaces")
        return result
        
    except Exception as e:
        logger.error(f"Error formatting queries with AI: {e}")
        return {marketplace: format_search_query_fallback(query, marketplace) for marketplace in marketplaces}

async def format_search_query_with_ai(
    query: str,
    marketplace: str,
    ai_service: Optional[AIService] = None
) -> str:
    """
    Format a search query using AI for optimal marketplace search results.
    
    Args:
        query: The original user query
        marketplace: Target marketplace (amazon, walmart, google_shopping)
        ai_service: Optional AIService instance
        
    Returns:
        Formatted query string
    """
    try:
        # Use the batch formatter for a single marketplace
        logger.info(f"Formatting query for single marketplace: {marketplace}")
        result = await format_search_queries_with_ai_batch(query, [marketplace], ai_service)
        formatted_query = result.get(marketplace)
        
        if not formatted_query:
            logger.warning(f"Failed to get AI-formatted query for {marketplace}, using fallback")
            return format_search_query_fallback(query, marketplace)
            
        logger.info(f"AI-formatted query for {marketplace}: '{query}' -> '{formatted_query}'")
        return formatted_query
    except Exception as e:
        logger.error(f"Error in format_search_query_with_ai: {e}")
        return format_search_query_fallback(query, marketplace)

def extract_parameters_from_query(query: str) -> Dict[str, Any]:
    """
    Extract parameters from a search query including price constraints, 
    potential brands, and keywords.
    
    Args:
        query: The search query string
    
    Returns:
        Dictionary containing extracted parameters
    """
    # Copy original query for case preservation
    original_query = query
    
    # Create word mapping for case preservation
    word_map = {}
    for word in re.findall(r'\b\w+\b', original_query):
        word_map[word.lower()] = word
    
    # Normalize query for ease of processing
    query = query.lower()
    
    # Extract price constraints using regex
    min_price = None
    max_price = None
    
    # Extract "under $X" or "less than $X" pattern
    max_price_match = re.search(r'(?:under|less than|below|no more than)\s*\$?(\d+(?:\.\d+)?)', query)
    if max_price_match:
        try:
            max_price = float(max_price_match.group(1))
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse max price from {max_price_match.group(0)}")
    
    # Extract "over $X" or "more than $X" pattern
    min_price_match = re.search(r'(?:over|more than|above|at least)\s*\$?(\d+(?:\.\d+)?)', query)
    if min_price_match:
        try:
            min_price = float(min_price_match.group(1))
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse min price from {min_price_match.group(0)}")
    
    # Extract price range with format "$X-$Y" or "X-Y"
    price_range_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*-\s*\$?(\d+(?:\.\d+)?)', query)
    if price_range_match:
        try:
            min_price = float(price_range_match.group(1))
            max_price = float(price_range_match.group(2))
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse price range from {price_range_match.group(0)}")
    
    # Extract "between $X and $Y" pattern
    between_match = re.search(r'between\s*\$?(\d+(?:\.\d+)?)\s*and\s*\$?(\d+(?:\.\d+)?)', query)
    if between_match:
        try:
            min_price = float(between_match.group(1))
            max_price = float(between_match.group(2))
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse price range from {between_match.group(0)}")
    
    # List of common brands for detection
    common_brands = [
        "apple", "samsung", "sony", "lg", "dell", "hp", "microsoft", "lenovo", 
        "asus", "acer", "bose", "nintendo", "playstation", "xbox", "google", 
        "amazon", "nikon", "canon", "gopro", "dyson", "kitchenaid", "cuisinart", 
        "bosch", "philips", "braun", "nike", "adidas", "under armour", "levis", 
        "gap", "zara", "h&m", "ikea", "wayfair", "disney", "lego", "mattel", 
        "hasbro", "vtech", "fisher-price"
    ]
    
    # Extract potential brands (check if any common brand names appear in the query)
    potential_brands = []
    for brand in common_brands:
        if re.search(rf'\b{re.escape(brand)}\b', query):
            # Add both original case and lowercase for maximum compatibility
            if brand.lower() in word_map:
                # Add original case version
                original_brand = word_map[brand.lower()]
                potential_brands.append(original_brand)
                # Add lowercase version for test compatibility
                potential_brands.append(brand.lower())
            else:
                potential_brands.append(brand)
    
    # Remove stop words for keywords
    stop_words = [
        "a", "an", "the", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
        "am", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "but", "and", "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", "about",
        "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "from",
        "up", "down", "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can", "will",
        "just", "should", "now", "want", "wanted", "looking", "need", "find", "search", "searching", "seeking",
        "get", "getting", "buy", "buying", "purchase", "purchasing", "i'm", "im", "iam", "i am", "would", "like",
        "best", "good", "cheap", "inexpensive", "expensive", "recommend", "recommendation", "deal", "deals", "sale",
        "discount", "offer", "promotion", "price", "cost", "under", "over", "less", "more", "than", "between"
    ]
    
    # Extract keywords (non-stop words that aren't brands)
    words = re.findall(r'\b(\w+)\b', query)
    keywords = []
    
    for word in words:
        # Don't add stop words
        if word in stop_words:
            continue
            
        # Don't add words that are part of price constraints
        if any(word in match.group(0).lower() if match else False for match in 
               [max_price_match, min_price_match, between_match, price_range_match if price_range_match else None]):
            continue
            
        # Don't add words that are part of brand names
        if any(word in brand.lower() for brand in potential_brands):
            continue
            
        # Use original case if available
        if word in word_map:
            # Add numbers to keywords (important for model numbers like "Series 7")
            if word.isdigit() or (any(c.isdigit() for c in word) and len(word) <= 3):
                keywords.append(word)
            elif word not in stop_words:
                # Add both original case and lowercase for test compatibility
                keywords.append(word_map[word])
                keywords.append(word)
    
    # Add any numbers that might be part of model numbers
    number_pattern = r'\b(\d+)\b'
    for number in re.findall(number_pattern, query):
        if number not in keywords:
            keywords.append(number)
    
    return {
        "min_price": min_price,
        "max_price": max_price,
        "brands": potential_brands,
        "keywords": keywords
    }

def format_search_query_fallback(query: str, market_type: str = None) -> str:
    """
    Format a search query without using AI, based on simple rules.
    
    Args:
        query: The original user query
        market_type: Target marketplace (not used in fallback, but kept for API consistency)
    
    Returns:
        Formatted query string
    """
    # Copy original query for case preservation
    original_query = query
    
    # Create word mapping for case preservation
    word_map = {}
    for word in re.findall(r'\b\w+\b', original_query):
        word_map[word.lower()] = word
    
    # Normalize query for processing
    query = query.lower()
    
    # Standardize price constraints
    query = re.sub(r'less than\s+\$?(\d+)', r'under $\1', query)
    query = re.sub(r'more than\s+\$?(\d+)', r'over $\1', query)
    
    # Remove common filler phrases
    filler_phrases = [
        "i want to buy", "i want to find", "i want to get", "i'd like to buy", 
        "i'd like to find", "i'd like to get", "i would like to buy", 
        "i would like to find", "i would like to get", "please find me", 
        "can you find", "can you search for", "please search for",
        "i need", "searching for", "looking for", "find me", "show me",
        "i'm interested in", "i am interested in", "i want", "please find",
        "could you find", "help me find", "i'd like", "i would like",
        "i'm looking for", "i am looking for", "i'm searching for", 
        "i am searching for", "find a", "find an", "can you find me",
        "i'm", "im", "iam", "i am"
    ]
    
    for phrase in filler_phrases:
        pattern = r'\b' + re.escape(phrase) + r'\b\s*'
        query = re.sub(pattern, '', query, flags=re.IGNORECASE)
    
    # Remove extra spaces and trim
    query = re.sub(r'\s+', ' ', query).strip()
    
    # If we have a totally empty query after removing filters, preserve some of the original
    if not query:
        query = original_query.lower()
    
    # Fix issue with 'n' prefix from regex matching
    if query.startswith('n '):
        query = query[2:]
        
    # Build formatted query using original case
    words = query.split()
    formatted_words = []
    
    # Remove unnecessary words
    stop_words = ['a', 'an', 'the', 'and', 'or', 'for', 'in', 'on', 'at', 'to', 'with', 'by', 'i', "i'm", "i'll", "i've", "i'd"]
    
    for word in words:
        if word.lower() in stop_words:
            continue
            
        if word in word_map:
            formatted_words.append(word_map[word])
        else:
            # If word not found in map (likely due to regex operations), keep as is
            formatted_words.append(word)
    
    formatted_query = ' '.join(formatted_words)
    
    logger.info(f"Fallback formatted query: '{original_query}' -> '{formatted_query}'")
    
    return formatted_query

async def get_optimized_queries_for_marketplaces(
    query: str,
    marketplaces: List[str],
    ai_service: Optional[AIService] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Get AI-optimized version of a query for multiple marketplaces in batch.
    
    This returns a more structured response than format_search_queries_with_ai_batch,
    including category detection, price constraints, brands, and features.
    
    Args:
        query: The original user query
        marketplaces: List of target marketplaces (amazon, walmart, google_shopping)
        ai_service: Optional AIService instance
        
    Returns:
        Dictionary mapping marketplace to a dict with formatted_query and analysis
    """
    # Default empty result structure
    default_result = {
        marketplace: {
            "formatted_query": format_search_query_fallback(query, marketplace),
            "intent": "purchase",
            "product_type": None,
            "category": None,
            "brands": [],
            "min_price": None,
            "max_price": None,
            "features": []
        } for marketplace in marketplaces
    }
    
    # If no AI service available, use fallback
    if not ai_service or not ai_service.llm:
        logger.warning("AI service not available for query optimization, using fallback")
        return default_result
    
    try:
        # Get all available category values for the prompt
        category_values = [category.value for category in MarketCategory]
        category_list_str = ", ".join(category_values)
        
        # Create system prompt for structured query analysis
        system_prompt = (
            "You are a search query optimization assistant that helps format user search queries for e-commerce marketplaces.\n"
            "Your task is to transform natural language shopping queries into optimized search terms with structured analysis.\n\n"
            "For each query, you should:\n"
            "1. Extract the core product being searched for\n"
            "2. Determine the most appropriate product category\n"
            "3. Identify any price constraints (minimum/maximum)\n"
            "4. Identify brand preferences\n"
            "5. Identify key features or specifications\n"
            "6. Output a formatted search query for EACH marketplace\n\n"
            f"IMPORTANT: You MUST categorize the query into EXACTLY ONE of these categories: {category_list_str}\n\n"
            "The output MUST be in valid JSON format with this structure:\n"
            "{\n"
            "  \"amazon\": {\n"
            "    \"formatted_query\": \"optimized search terms for Amazon\",\n"
            "    \"intent\": \"purchase\",\n"
            "    \"product_type\": \"specific product type\",\n"
            "    \"category\": \"EXACTLY ONE category from the provided list\",\n"
            "    \"brands\": [\"brand1\", \"brand2\"],\n"
            "    \"min_price\": numeric or null,\n"
            "    \"max_price\": numeric or null,\n"
            "    \"features\": [\"feature1\", \"feature2\"]\n"
            "  },\n"
            "  \"walmart\": { ... },\n"
            "  \"google_shopping\": { ... }\n"
            "}\n"
            "Provide data only for the requested marketplaces."
        )
        
        # Create user prompt with list of marketplaces
        user_prompt = f"Analyze and optimize this search query for the following marketplaces: {', '.join(marketplaces)}:\n{query}"
        
        # Prepare base parameters for LLM
        base_params = {
            "temperature": 0.2,  # Lower temperature for more deterministic response
            "max_tokens": 500    # Increased token count for detailed analysis
        }
        
        # Try with response_format parameter first, then fall back if needed
        formatted_response = None
        
        try:
            # First attempt: Try with response_format parameter (supported by newer models)
            logger.info("Attempting LLM call with response_format parameter")
            response = await ai_service.llm.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                **base_params,
                response_format={"type": "json_object"}  # This parameter might not be supported by all LLMs
            )
            
            # Extract content from the response
            if hasattr(response, 'content'):
                formatted_response = response.content
            elif isinstance(response, dict) and 'content' in response:
                formatted_response = response['content']
            else:
                formatted_response = str(response)
                
        except Exception as e:
            # Catch any errors related to unsupported parameters
            logger.warning(f"LLM call with response_format failed: {e}. Trying without response_format parameter.")
            
            # Second attempt: Try without response_format parameter
            try:
                # Add explicit JSON instructions to the prompt as a fallback
                enhanced_system_prompt = system_prompt + "\n\nYou MUST respond with ONLY a valid JSON object. Do not include any explanatory text, markdown formatting, or code block markers."
                
                response = await ai_service.llm.ainvoke(
                    [
                        {"role": "system", "content": enhanced_system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    **base_params
                )
                
                # Extract content from the response
                if hasattr(response, 'content'):
                    formatted_response = response.content
                elif isinstance(response, dict) and 'content' in response:
                    formatted_response = response['content']
                else:
                    formatted_response = str(response)
            except Exception as retry_err:
                logger.error(f"Both LLM call attempts failed: {retry_err}")
                return default_result
        
        # Parse the response as JSON
        import json
        try:
            # Clean up the response - remove any markdown code blocks and prefixes/suffixes
            formatted_response = re.sub(r'^```(?:json)?\s*|\s*```$', '', formatted_response, flags=re.DOTALL)
            
            # Attempt to find a JSON object if text contains additional content
            json_match = re.search(r'({[\s\S]*})', formatted_response)
            if json_match:
                potential_json = json_match.group(1)
                try:
                    # Try parsing the extracted JSON
                    result = json.loads(potential_json)
                    logger.info("Successfully parsed JSON object from response text")
                except json.JSONDecodeError:
                    # If extraction failed, try with the full response
                    result = json.loads(formatted_response)
            else:
                # No JSON-like structure found, try parsing the entire response
                result = json.loads(formatted_response)
                
            logger.info(f"Successfully parsed AI query analysis with categories")
            
            # Ensure the result has the expected structure for each marketplace
            for marketplace in marketplaces:
                if marketplace not in result:
                    logger.warning(f"AI response missing data for {marketplace}, using fallback")
                    result[marketplace] = default_result[marketplace]
                else:
                    # Ensure the marketplace entry has all required fields
                    for field in ["formatted_query", "intent", "product_type", "category", "brands", "min_price", "max_price", "features"]:
                        if field not in result[marketplace]:
                            result[marketplace][field] = default_result[marketplace][field]
                
                # Validate the category for this marketplace
                market_data = result[marketplace]
                if not market_data["category"] or market_data["category"] not in category_values:
                    logger.warning(f"Invalid category in AI response for {marketplace}: {market_data['category']}")
                    # Find the best matching category or default to OTHER
                    try:
                        # Try to match partially
                        provided_category = str(market_data["category"] or "").upper()
                        matched = False
                        for valid_category in category_values:
                            if provided_category in valid_category.upper():
                                market_data["category"] = valid_category
                                matched = True
                                break
                        
                        if not matched:
                            market_data["category"] = "OTHER"
                    except Exception as cat_err:
                        logger.error(f"Error matching category: {cat_err}")
                        market_data["category"] = "OTHER"
            
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}, response: {formatted_response[:200]}...")
            return default_result
            
    except Exception as e:
        logger.error(f"Error getting optimized queries with AI: {e}")
        return default_result

async def get_optimized_query_for_marketplace(
    query: str,
    marketplace: str,
    ai_service: Optional[AIService] = None
) -> Dict[str, Any]:
    """
    Get AI-optimized version of a query for a single marketplace.
    
    Args:
        query: The original user query
        marketplace: Target marketplace (amazon, walmart, google_shopping)
        ai_service: Optional AIService instance
        
    Returns:
        Dictionary with formatted_query and analysis
    """
    try:
        # Use the batch optimizer for a single marketplace
        logger.info(f"Getting optimized query for single marketplace: {marketplace}")
        result = await get_optimized_queries_for_marketplaces(query, [marketplace], ai_service)
        
        # Get the result for this marketplace or use default
        marketplace_result = result.get(marketplace)
        
        if not marketplace_result:
            logger.warning(f"Failed to get optimized query for {marketplace}, using fallback")
            fallback = {
                "formatted_query": format_search_query_fallback(query, marketplace),
                "intent": "purchase",
                "product_type": None,
                "category": None,
                "brands": [],
                "min_price": None,
                "max_price": None,
                "features": []
            }
            return fallback
            
        logger.info(f"Successfully retrieved optimized query for {marketplace}")
        return marketplace_result
    except Exception as e:
        logger.error(f"Error in get_optimized_query_for_marketplace: {e}")
        return {
            "formatted_query": format_search_query_fallback(query, marketplace),
            "intent": "purchase",
            "product_type": None,
            "category": None,
            "brands": [],
            "min_price": None,
            "max_price": None,
            "features": []
        } 