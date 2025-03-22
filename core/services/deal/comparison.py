"""Deal comparison module.

This module provides functionality for comparing deals.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from core.exceptions import (
    DealNotFoundError,
    InvalidDealDataError,
    ExternalServiceError
)

logger = logging.getLogger(__name__)

async def compare_deals(
    self,
    deal_ids: List[UUID],
    user_id: UUID,
    comparison_type: str = "price",
    criteria: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Compare multiple deals using specified criteria.
    
    Args:
        deal_ids: List of deal IDs to compare
        user_id: User making the comparison request
        comparison_type: Type of comparison (price, features, value, overall)
        criteria: Optional custom criteria for comparison
        
    Returns:
        Dictionary with comparison results
        
    Raises:
        InvalidDealDataError: If invalid deals or criteria
        ExternalServiceError: If comparison fails
    """
    try:
        logger.info(f"Comparing {len(deal_ids)} deals with comparison_type: {comparison_type}")
        
        # Limit number of deals to compare
        if len(deal_ids) > 10:
            raise InvalidDealDataError("Cannot compare more than 10 deals at once")
            
        if len(deal_ids) < 2:
            raise InvalidDealDataError("Need at least 2 deals to compare")
            
        # Validate comparison type
        valid_types = ["price", "features", "value", "overall"]
        if comparison_type not in valid_types:
            logger.warning(f"Invalid comparison type: {comparison_type}")
            comparison_type = "price"  # Default to price comparison
            
        # Get deal data for each deal ID
        deals = []
        for deal_id in deal_ids:
            deal = await self._repository.get_by_id(deal_id)
            if not deal:
                raise DealNotFoundError(f"Deal {deal_id} not found")
                
            # Convert to response format
            deal_dict = self._convert_to_response(deal, user_id)
            deals.append(deal_dict)
            
        # Initialize default criteria if not provided
        if not criteria:
            criteria = {
                "price_weight": 0.4,
                "features_weight": 0.3,
                "rating_weight": 0.2,
                "recency_weight": 0.1,
                "important_features": []
            }
            
        # Perform comparison based on type
        comparison_result = {}
        if comparison_type == "price":
            comparison_result = await self._compare_by_price(deals, criteria)
        elif comparison_type == "features":
            comparison_result = await self._compare_by_features(deals, criteria)
        elif comparison_type == "value":
            comparison_result = await self._compare_by_value(deals, criteria)
        elif comparison_type == "overall":
            comparison_result = await self._compare_overall(deals, criteria)
            
        # Add metadata to result
        result = {
            "comparison_id": str(UUID.uuid4()),
            "user_id": str(user_id),
            "comparison_type": comparison_type,
            "criteria": criteria,
            "timestamp": datetime.utcnow().isoformat(),
            "deal_count": len(deals),
            "deal_ids": [str(deal_id) for deal_id in deal_ids],
            "results": comparison_result
        }
        
        logger.info(f"Comparison completed for {len(deals)} deals")
        return result
        
    except DealNotFoundError:
        raise
    except InvalidDealDataError:
        raise
    except Exception as e:
        logger.error(f"Error during deal comparison: {str(e)}")
        raise ExternalServiceError(
            service="deal_service",
            operation="compare_deals",
            message=f"Failed to compare deals: {str(e)}"
        )

async def _compare_by_price(
    self, 
    deals: List[Dict[str, Any]], 
    criteria: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare deals based on price and discounts.
    
    Args:
        deals: List of deal dictionaries to compare
        criteria: Criteria for comparison
        
    Returns:
        Comparison results focusing on price
    """
    try:
        # Sort deals by price (lowest first)
        sorted_deals = sorted(
            deals,
            key=lambda d: float(d.get("price", "999999"))
        )
        
        # Calculate price differences
        lowest_price = float(sorted_deals[0].get("price", "0"))
        
        # Process each deal
        comparison_results = []
        for deal in sorted_deals:
            price = float(deal.get("price", "0"))
            original_price = float(deal.get("original_price", "0")) if deal.get("original_price") else price
            
            # Calculate price metrics
            price_difference = price - lowest_price
            price_difference_pct = (price_difference / lowest_price * 100) if lowest_price > 0 else 0
            
            # Calculate discount percentage
            discount_pct = 0
            if original_price > 0 and price < original_price:
                discount_pct = (original_price - price) / original_price * 100
                
            # Get price history if available
            price_history = []
            if "price_history" in deal:
                price_history = deal["price_history"]
                
            # Create result entry
            result = {
                "deal_id": deal.get("id"),
                "title": deal.get("title"),
                "price": price,
                "currency": deal.get("currency", "USD"),
                "original_price": original_price if original_price != price else None,
                "discount_percentage": f"{discount_pct:.2f}%" if discount_pct > 0 else None,
                "price_difference": price_difference if price_difference > 0 else 0,
                "price_difference_percentage": f"{price_difference_pct:.2f}%" if price_difference_pct > 0 else "0%",
                "is_lowest_price": price == lowest_price
            }
            
            # Add price history trend if available
            if "price_history" in deal and len(price_history) > 1:
                trend = self._calculate_price_trend(price_history)
                result["price_trend"] = trend
                
            comparison_results.append(result)
            
        # Find best value (highest discount)
        best_value = max(
            comparison_results,
            key=lambda d: float(d.get("discount_percentage", "0").replace("%", "")) if d.get("discount_percentage") else 0
        )
        
        # Return structured result
        return {
            "lowest_price": {
                "deal_id": sorted_deals[0].get("id"),
                "title": sorted_deals[0].get("title"),
                "price": float(sorted_deals[0].get("price", "0")),
                "currency": sorted_deals[0].get("currency", "USD")
            },
            "best_value": {
                "deal_id": best_value.get("deal_id"),
                "title": best_value.get("title"),
                "price": best_value.get("price"),
                "original_price": best_value.get("original_price"),
                "discount_percentage": best_value.get("discount_percentage")
            },
            "price_range": {
                "min": float(sorted_deals[0].get("price", "0")),
                "max": float(sorted_deals[-1].get("price", "0")),
                "difference": float(sorted_deals[-1].get("price", "0")) - float(sorted_deals[0].get("price", "0")),
                "difference_percentage": f"{((float(sorted_deals[-1].get('price', '0')) - float(sorted_deals[0].get('price', '0'))) / float(sorted_deals[0].get('price', '1')) * 100):.2f}%"
            },
            "details": comparison_results
        }
        
    except Exception as e:
        logger.error(f"Error in price comparison: {str(e)}")
        return {
            "error": f"Failed to compare prices: {str(e)}",
            "details": []
        }

async def _compare_by_features(
    self, 
    deals: List[Dict[str, Any]], 
    criteria: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare deals based on features and specifications.
    
    Args:
        deals: List of deal dictionaries to compare
        criteria: Criteria for comparison
        
    Returns:
        Comparison results focusing on features
    """
    try:
        # Extract features from descriptions
        for deal in deals:
            features = self._extract_features_from_description(deal.get("description", ""))
            deal["extracted_features"] = features
            
        # Get important features from criteria
        important_features = criteria.get("important_features", [])
        
        # Create feature matrix
        feature_matrix = []
        all_features = set()
        
        # Collect all unique features across deals
        for deal in deals:
            all_features.update(deal.get("extracted_features", []))
            
        # Add important features that might not be in extracted features
        all_features.update(important_features)
        
        # For each deal, check which features it has
        for deal in deals:
            deal_features = deal.get("extracted_features", [])
            
            feature_entry = {
                "deal_id": deal.get("id"),
                "title": deal.get("title"),
                "features": {}
            }
            
            # Mark each feature as present or not
            for feature in all_features:
                has_feature = any(f.lower() in feature.lower() or feature.lower() in f.lower() for f in deal_features)
                feature_entry["features"][feature] = has_feature
                
            # Count total features
            feature_entry["feature_count"] = sum(1 for f in feature_entry["features"].values() if f)
            
            # Count important features
            important_count = sum(1 for f in important_features if any(
                f.lower() in feat.lower() or feat.lower() in f.lower() for feat in deal_features
            ))
            feature_entry["important_feature_count"] = important_count
            
            feature_matrix.append(feature_entry)
            
        # Find deal with most features
        most_features = max(feature_matrix, key=lambda d: d["feature_count"]) if feature_matrix else None
        
        # Find deal with most important features
        most_important = max(feature_matrix, key=lambda d: d["important_feature_count"]) if feature_matrix and important_features else most_features
        
        # Return structured result
        return {
            "feature_count": {
                "deal_id": most_features.get("deal_id") if most_features else None,
                "title": most_features.get("title") if most_features else None,
                "feature_count": most_features.get("feature_count") if most_features else 0
            },
            "important_features": {
                "deal_id": most_important.get("deal_id") if most_important else None,
                "title": most_important.get("title") if most_important else None,
                "important_feature_count": most_important.get("important_feature_count") if most_important else 0
            },
            "feature_matrix": feature_matrix,
            "all_features": list(all_features)
        }
        
    except Exception as e:
        logger.error(f"Error in feature comparison: {str(e)}")
        return {
            "error": f"Failed to compare features: {str(e)}",
            "details": []
        }

async def _compare_by_value(
    self, 
    deals: List[Dict[str, Any]], 
    criteria: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare deals based on overall value (price vs. features).
    
    Args:
        deals: List of deal dictionaries to compare
        criteria: Criteria for comparison
        
    Returns:
        Comparison results focusing on value
    """
    try:
        # Extract features from descriptions
        for deal in deals:
            features = self._extract_features_from_description(deal.get("description", ""))
            deal["extracted_features"] = features
            
        # Get weights from criteria
        price_weight = criteria.get("price_weight", 0.4)
        features_weight = criteria.get("features_weight", 0.3)
        rating_weight = criteria.get("rating_weight", 0.2)
        recency_weight = criteria.get("recency_weight", 0.1)
        
        # Calculate price scores (lower is better)
        prices = [float(deal.get("price", "0")) for deal in deals]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        price_range = max_price - min_price if max_price > min_price else 1
        
        # Calculate feature counts
        for deal in deals:
            deal["feature_count"] = len(deal.get("extracted_features", []))
            
        feature_counts = [deal.get("feature_count", 0) for deal in deals]
        max_features = max(feature_counts) if feature_counts else 1
        
        # Calculate value scores
        value_results = []
        for deal in deals:
            # Price score (0-100, higher is better)
            price = float(deal.get("price", "0"))
            price_score = 100 - ((price - min_price) / price_range * 100) if price_range > 0 else 50
            
            # Feature score (0-100, higher is better)
            feature_count = deal.get("feature_count", 0)
            feature_score = (feature_count / max_features * 100) if max_features > 0 else 50
            
            # Rating score (0-100, higher is better)
            rating = 0
            if "seller_info" in deal and "rating" in deal["seller_info"]:
                rating = float(deal["seller_info"]["rating"]) if deal["seller_info"]["rating"] else 0
            rating_score = (rating / 5 * 100) if rating > 0 else 50  # Assuming 5 is max rating
            
            # Recency score (0-100, higher is better)
            recency_score = 50  # Default
            if "created_at" in deal:
                try:
                    created_date = datetime.fromisoformat(deal["created_at"])
                    days_old = (datetime.utcnow() - created_date).days
                    recency_score = max(0, 100 - (days_old * 2))  # Lose 2 points per day
                except Exception:
                    pass
                    
            # Calculate weighted score
            weighted_score = (
                price_score * price_weight +
                feature_score * features_weight +
                rating_score * rating_weight +
                recency_score * recency_weight
            )
            
            # Add to results
            value_results.append({
                "deal_id": deal.get("id"),
                "title": deal.get("title"),
                "price": price,
                "feature_count": feature_count,
                "price_score": round(price_score, 2),
                "feature_score": round(feature_score, 2),
                "rating_score": round(rating_score, 2),
                "recency_score": round(recency_score, 2),
                "weighted_score": round(weighted_score, 2)
            })
            
        # Sort by weighted score (highest first)
        sorted_results = sorted(
            value_results,
            key=lambda d: d["weighted_score"],
            reverse=True
        )
        
        # Return structured result
        return {
            "best_value": {
                "deal_id": sorted_results[0]["deal_id"] if sorted_results else None,
                "title": sorted_results[0]["title"] if sorted_results else None,
                "weighted_score": sorted_results[0]["weighted_score"] if sorted_results else 0
            },
            "weights_used": {
                "price_weight": price_weight,
                "features_weight": features_weight,
                "rating_weight": rating_weight,
                "recency_weight": recency_weight
            },
            "details": sorted_results
        }
        
    except Exception as e:
        logger.error(f"Error in value comparison: {str(e)}")
        return {
            "error": f"Failed to compare value: {str(e)}",
            "details": []
        }

async def _compare_overall(
    self, 
    deals: List[Dict[str, Any]], 
    criteria: Dict[str, Any]
) -> Dict[str, Any]:
    """Perform a comprehensive comparison of deals.
    
    Args:
        deals: List of deal dictionaries to compare
        criteria: Criteria for comparison
        
    Returns:
        Comprehensive comparison results
    """
    try:
        # Perform individual comparisons
        price_comparison = await self._compare_by_price(deals, criteria)
        features_comparison = await self._compare_by_features(deals, criteria)
        value_comparison = await self._compare_by_value(deals, criteria)
        
        # Get best deals from each category
        best_price_deal_id = price_comparison.get("lowest_price", {}).get("deal_id")
        best_value_deal_id = value_comparison.get("best_value", {}).get("deal_id")
        best_features_deal_id = features_comparison.get("feature_count", {}).get("deal_id")
        
        # Count votes for each deal
        deal_votes = {}
        for deal_id in [best_price_deal_id, best_value_deal_id, best_features_deal_id]:
            if deal_id:
                deal_votes[deal_id] = deal_votes.get(deal_id, 0) + 1
                
        # Find overall winner (most votes)
        overall_winner_id = max(deal_votes.items(), key=lambda x: x[1])[0] if deal_votes else None
        
        # Get details for overall winner
        overall_winner = None
        if overall_winner_id:
            for deal in deals:
                if deal.get("id") == overall_winner_id:
                    overall_winner = {
                        "deal_id": deal.get("id"),
                        "title": deal.get("title"),
                        "price": float(deal.get("price", "0")),
                        "votes": deal_votes[overall_winner_id]
                    }
                    break
                    
        # Generate personalized recommendations
        recommendations = []
        
        # Always recommend the overall winner
        if overall_winner:
            recommendations.append({
                "deal_id": overall_winner["deal_id"],
                "title": overall_winner["title"],
                "reason": "Best overall value based on your criteria"
            })
            
        # If budget is important, recommend lowest price
        if price_comparison.get("lowest_price") and price_comparison["lowest_price"].get("deal_id") != overall_winner_id:
            recommendations.append({
                "deal_id": price_comparison["lowest_price"]["deal_id"],
                "title": price_comparison["lowest_price"]["title"],
                "reason": "Lowest price option"
            })
            
        # If features are important, recommend most features
        if features_comparison.get("feature_count") and features_comparison["feature_count"].get("deal_id") != overall_winner_id:
            recommendations.append({
                "deal_id": features_comparison["feature_count"]["deal_id"],
                "title": features_comparison["feature_count"]["title"],
                "reason": "Most complete feature set"
            })
            
        # Generate AI-based comparison insights
        insights = []
        
        # Price insights
        if price_comparison.get("price_range") and price_comparison["price_range"].get("difference"):
            price_diff = price_comparison["price_range"]["difference"]
            price_diff_pct = price_comparison["price_range"]["difference_percentage"]
            insights.append(f"Price range: The most expensive option is ${price_diff:.2f} ({price_diff_pct}) more than the cheapest option.")
            
        # Feature insights
        if features_comparison.get("all_features"):
            common_features = []
            unique_features = {}
            
            # Find common and unique features
            for deal in deals:
                deal_id = deal.get("id")
                deal_features = deal.get("extracted_features", [])
                
                # Track unique features by deal
                if deal_id and deal_features:
                    unique_features[deal_id] = []
                    for feature in deal_features:
                        # Check if this feature is unique to this deal
                        is_unique = True
                        for other_deal in deals:
                            if other_deal.get("id") != deal_id:
                                other_features = other_deal.get("extracted_features", [])
                                if any(f.lower() in feature.lower() or feature.lower() in f.lower() for f in other_features):
                                    is_unique = False
                                    break
                        if is_unique:
                            unique_features[deal_id].append(feature)
                            
            # Add insights about unique features
            for deal_id, features in unique_features.items():
                if features:
                    deal_title = next((d["title"] for d in deals if d.get("id") == deal_id), "This option")
                    if len(features) <= 3:
                        insight = f"{deal_title} uniquely offers: {', '.join(features)}"
                    else:
                        insight = f"{deal_title} has {len(features)} unique features including: {', '.join(features[:3])}..."
                    insights.append(insight)
                    
        # Return comprehensive results
        return {
            "overall_winner": overall_winner,
            "category_winners": {
                "price": {
                    "deal_id": best_price_deal_id,
                    "title": price_comparison.get("lowest_price", {}).get("title"),
                    "price": price_comparison.get("lowest_price", {}).get("price")
                },
                "features": {
                    "deal_id": best_features_deal_id,
                    "title": features_comparison.get("feature_count", {}).get("title"),
                    "feature_count": features_comparison.get("feature_count", {}).get("feature_count")
                },
                "value": {
                    "deal_id": best_value_deal_id,
                    "title": value_comparison.get("best_value", {}).get("title"),
                    "weighted_score": value_comparison.get("best_value", {}).get("weighted_score")
                }
            },
            "recommendations": recommendations,
            "insights": insights,
            "comparison_details": {
                "price": price_comparison,
                "features": features_comparison,
                "value": value_comparison
            }
        }
        
    except Exception as e:
        logger.error(f"Error in overall comparison: {str(e)}")
        return {
            "error": f"Failed to perform overall comparison: {str(e)}",
            "details": []
        }

def _extract_features_from_description(self, description: str) -> List[str]:
    """Extract product features from a description.
    
    Args:
        description: Product description text
        
    Returns:
        List of extracted features
    """
    if not description:
        return []
        
    features = []
    
    # Look for bullet points
    bullet_pattern = r'(?:^|\n)(?:[\s\-\*•‣⁃▪▹►➢➤⟐⟡⦿⦿⦿]+)([^\n\r]+)'
    bullets = re.findall(bullet_pattern, description)
    if bullets:
        features.extend([b.strip() for b in bullets if len(b.strip()) > 5])
        
    # Look for features in "features:", "specifications:", etc.
    feature_sections = re.split(r'(?i)(?:features|specifications|specs|details|product info)[\s\-:]+', description)
    if len(feature_sections) > 1:
        potential_features = feature_sections[1].split('\n')
        features.extend([f.strip() for f in potential_features if len(f.strip()) > 5 and ':' in f])
        
    # Look for technical specifications
    tech_pattern = r'([A-Za-z0-9 ]+):[ \t]*([A-Za-z0-9 ]+)'
    tech_specs = re.findall(tech_pattern, description)
    if tech_specs:
        features.extend([f"{k.strip()}: {v.strip()}" for k, v in tech_specs])
        
    # Look for dimensions and measurements
    dimension_pattern = r'\b(\d+(?:\.\d+)?[ \t]*(?:inches|in|cm|mm|feet|ft|m|kg|lb|lbs|oz|grams|g))\b'
    dimensions = re.findall(dimension_pattern, description)
    features.extend([d.strip() for d in dimensions])
    
    # Look for technical terms
    tech_terms = [
        "wireless", "bluetooth", "wifi", "usb", "hdmi", "4k", "ultra hd", "hd", "smart", 
        "touchscreen", "waterproof", "rechargeable", "portable", "digital", "automatic", 
        "cordless", "stainless steel", "aluminum", "memory", "storage", "processor", 
        "battery", "camera", "display", "screen", "resolution", "warranty"
    ]
    
    for term in tech_terms:
        pattern = r'\b' + term + r'(?:[- ][A-Za-z0-9]+){0,3}\b'
        matches = re.findall(pattern, description.lower())
        features.extend([m.strip() for m in matches])
        
    # Remove duplicates and very short features
    unique_features = []
    for feature in features:
        feature = feature.strip()
        # Skip empty or very short features
        if not feature or len(feature) < 3:
            continue
            
        # Check if this feature is a duplicate
        is_duplicate = False
        for existing in unique_features:
            # Check for exact match or substring
            if feature.lower() == existing.lower() or feature.lower() in existing.lower():
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_features.append(feature)
            
    return unique_features 