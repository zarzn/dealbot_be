"""Deal goals module.

This module provides functionality for matching deals with user goals.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timedelta
import json
import re
from enum import Enum

from core.exceptions import (
    GoalNotFoundError,
    InvalidGoalDataError,
    DealNotFoundError
)
from core.models.enums import GoalStatus, DealStatus

# Define MatchScore locally since it's not in core.models.enums
class MatchScore(str, Enum):
    """Match score enum for goal matches."""
    PERFECT = "perfect"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

logger = logging.getLogger(__name__)

# Constants
GOAL_MATCH_THRESHOLD = 0.7  # Minimum match score (0.0-1.0) to consider a deal match for a goal
GOAL_SCAN_INTERVAL = 3600  # 1 hour in seconds
MAX_GOAL_MATCHES = 10  # Maximum number of deals to match per goal

async def match_deals_to_goal(
    self,
    goal_id: UUID,
    max_matches: int = MAX_GOAL_MATCHES,
    min_score: float = GOAL_MATCH_THRESHOLD,
    automatic_notify: bool = True
) -> Dict[str, Any]:
    """Match deals to a user goal.
    
    Args:
        goal_id: The ID of the goal to match deals for
        max_matches: Maximum number of deals to return
        min_score: Minimum match score threshold
        automatic_notify: Whether to notify the user of matches
        
    Returns:
        Dictionary with matched deals and scores
        
    Raises:
        GoalNotFoundError: If goal not found
    """
    try:
        # Get goal from goal service
        goal = await self._goal_service.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")
            
        # Check if goal is active
        if goal.status != GoalStatus.ACTIVE.value:
            logger.warning(f"Attempted to match deals to inactive goal {goal_id} with status {goal.status}")
            return {
                "goal_id": str(goal_id),
                "status": "inactive",
                "matches": []
            }
            
        # Extract goal details
        goal_data = {
            "id": goal.id,
            "user_id": goal.user_id,
            "title": goal.title,
            "description": goal.description,
            "price_min": goal.price_min,
            "price_max": goal.price_max,
            "category": goal.category,
            "keywords": goal.keywords,
            "created_at": goal.created_at
        }
        
        # Find matching deals
        matching_deals = await self._find_matching_deals(goal_data, max_matches, min_score)
        
        # Sort by match score
        matching_deals.sort(key=lambda x: x["match_score"], reverse=True)
        
        # Store matches in Redis
        matches_key = f"goal:{goal_id}:matches"
        match_ids = [str(match["deal_id"]) for match in matching_deals]
        
        if match_ids:
            # Store all match IDs
            await self._redis_client.delete(matches_key)
            await self._redis_client.sadd(matches_key, *match_ids)
            
            # Store individual match scores
            for match in matching_deals:
                await self._redis_client.set(
                    f"goal:{goal_id}:match:{match['deal_id']}",
                    json.dumps({
                        "score": match["match_score"],
                        "reasons": match["match_reasons"],
                        "matched_at": datetime.utcnow().isoformat()
                    }),
                    ex=86400 * 30  # 30 days TTL
                )
            
        # Notify user of new matches if requested
        if automatic_notify and matching_deals:
            # Get previously notified matches
            notified_matches_key = f"goal:{goal_id}:notified_matches"
            notified_match_ids = await self._redis_client.smembers(notified_matches_key) or set()
            
            # Filter to only new matches
            new_matches = [
                match for match in matching_deals
                if str(match["deal_id"]) not in notified_match_ids
            ]
            
            if new_matches:
                # Add to notified set
                new_match_ids = [str(match["deal_id"]) for match in new_matches]
                await self._redis_client.sadd(notified_matches_key, *new_match_ids)
                
                # Send notification
                asyncio.create_task(self._notify_goal_matches(
                    goal_id, 
                    goal.user_id, 
                    new_matches,
                    goal.title
                ))
            
        return {
            "goal_id": str(goal_id),
            "match_count": len(matching_deals),
            "matches": matching_deals
        }
        
    except GoalNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error matching deals to goal {goal_id}: {str(e)}")
        raise GoalNotFoundError(f"Failed to match deals to goal: {str(e)}")

async def match_deal_to_goals(
    self,
    deal_id: UUID,
    min_score: float = GOAL_MATCH_THRESHOLD,
    automatic_notify: bool = True
) -> Dict[str, Any]:
    """Match a deal to user goals.
    
    Args:
        deal_id: The ID of the deal to match against goals
        min_score: Minimum match score threshold
        automatic_notify: Whether to notify users of matches
        
    Returns:
        Dictionary with matched goals and scores
        
    Raises:
        DealNotFoundError: If deal not found
    """
    try:
        # Get deal from repository
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Check if deal is active
        if deal.status != DealStatus.ACTIVE.value:
            logger.warning(f"Attempted to match inactive deal {deal_id} with status {deal.status}")
            return {
                "deal_id": str(deal_id),
                "status": "inactive",
                "matches": []
            }
            
        # Extract deal details
        deal_data = {
            "id": deal.id,
            "title": deal.title,
            "description": deal.description,
            "price": deal.price,
            "original_price": deal.original_price,
            "category": deal.category,
            "seller_info": deal.seller_info,
            "deal_metadata": deal.deal_metadata
        }
        
        # Get all active goals from goal service
        goals = await self._goal_service.list_goals(status=GoalStatus.ACTIVE.value)
        
        # Find matching goals
        matching_goals = []
        
        for goal in goals:
            # Calculate match score
            match_result = await self._calculate_goal_match(deal_data, goal)
            
            # Check if meets threshold
            if match_result["score"] >= min_score:
                matching_goals.append({
                    "goal_id": str(goal.id),
                    "user_id": str(goal.user_id),
                    "title": goal.title,
                    "match_score": match_result["score"],
                    "match_reasons": match_result["reasons"]
                })
                
                # Store match in Redis
                await self._redis_client.set(
                    f"goal:{goal.id}:match:{deal_id}",
                    json.dumps({
                        "score": match_result["score"],
                        "reasons": match_result["reasons"],
                        "matched_at": datetime.utcnow().isoformat()
                    }),
                    ex=86400 * 30  # 30 days TTL
                )
                
                # Add to goal's matches set
                await self._redis_client.sadd(f"goal:{goal.id}:matches", str(deal_id))
                
        # Sort by match score
        matching_goals.sort(key=lambda x: x["match_score"], reverse=True)
        
        # Notify users of matches if requested
        if automatic_notify and matching_goals:
            # Group by user
            user_matches = {}
            for match in matching_goals:
                user_id = match["user_id"]
                if user_id not in user_matches:
                    user_matches[user_id] = []
                user_matches[user_id].append(match)
                
            # Notify each user
            for user_id, matches in user_matches.items():
                # Get previously notified
                notified_key = f"user:{user_id}:deal:{deal_id}:notified"
                already_notified = await self._redis_client.get(notified_key)
                
                if not already_notified:
                    # Send notification and mark as notified
                    asyncio.create_task(self._notify_deal_matches(
                        deal_id,
                        UUID(user_id),
                        matches,
                        deal.title
                    ))
                    
                    await self._redis_client.set(notified_key, "1", ex=86400 * 7)  # 7 days TTL
            
        return {
            "deal_id": str(deal_id),
            "match_count": len(matching_goals),
            "matches": matching_goals
        }
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error matching deal {deal_id} to goals: {str(e)}")
        raise DealNotFoundError(f"Failed to match deal to goals: {str(e)}")

async def get_deal_matches_for_goal(
    self,
    goal_id: UUID,
    limit: int = 10,
    offset: int = 0
) -> Dict[str, Any]:
    """Get matches for a goal with pagination.
    
    Args:
        goal_id: The goal ID
        limit: Maximum number of matches to return
        offset: Number of matches to skip
        
    Returns:
        Dictionary with matched deals and pagination info
        
    Raises:
        GoalNotFoundError: If goal not found
    """
    try:
        # Validate goal exists
        goal = await self._goal_service.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")
            
        # Get all match IDs for goal from Redis
        matches_key = f"goal:{goal_id}:matches"
        match_ids = await self._redis_client.smembers(matches_key) or set()
        
        # Get total count
        total_count = len(match_ids)
        
        # Apply pagination
        paginated_ids = list(match_ids)[offset:offset+limit]
        
        # If no matches, return empty results
        if not paginated_ids:
            return {
                "goal_id": str(goal_id),
                "results": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False
            }
            
        # Get deals from database
        deal_ids = [UUID(match_id) for match_id in paginated_ids]
        deals = await self._repository.get_by_ids(deal_ids)
        
        # Get match scores and reasons
        results = []
        for deal in deals:
            # Get match details
            match_key = f"goal:{goal_id}:match:{deal.id}"
            match_json = await self._redis_client.get(match_key)
            
            if match_json:
                match_data = json.loads(match_json)
                score = match_data.get("score", 0)
                reasons = match_data.get("reasons", [])
                matched_at = match_data.get("matched_at")
            else:
                # If no stored score, recalculate
                match_result = await self._calculate_goal_match(
                    {
                        "id": deal.id,
                        "title": deal.title,
                        "description": deal.description,
                        "price": deal.price,
                        "original_price": deal.original_price,
                        "category": deal.category,
                        "seller_info": deal.seller_info,
                        "deal_metadata": deal.deal_metadata
                    },
                    goal
                )
                score = match_result["score"]
                reasons = match_result["reasons"]
                matched_at = datetime.utcnow().isoformat()
                
            # Add to results
            results.append({
                "deal_id": str(deal.id),
                "title": deal.title,
                "price": str(deal.price),
                "original_price": str(deal.original_price) if deal.original_price else None,
                "url": deal.url,
                "image_url": deal.image_url,
                "category": deal.category,
                "match_score": score,
                "match_reasons": reasons,
                "matched_at": matched_at
            })
            
        # Sort by match score
        results.sort(key=lambda x: x["match_score"], reverse=True)
        
        return {
            "goal_id": str(goal_id),
            "results": results,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }
        
    except GoalNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error getting deal matches for goal {goal_id}: {str(e)}")
        raise GoalNotFoundError(f"Failed to get deal matches for goal: {str(e)}")

async def get_goal_matches_for_deal(
    self,
    deal_id: UUID,
    limit: int = 10,
    offset: int = 0
) -> Dict[str, Any]:
    """Get goal matches for a deal with pagination.
    
    Args:
        deal_id: The deal ID
        limit: Maximum number of goals to return
        offset: Number of goals to skip
        
    Returns:
        Dictionary with matched goals and pagination info
        
    Raises:
        DealNotFoundError: If deal not found
    """
    try:
        # Validate deal exists
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Match deal to goals
        match_results = await self.match_deal_to_goals(
            deal_id,
            automatic_notify=False  # Don't notify on this call
        )
        
        # Get total count
        total_count = match_results["match_count"]
        
        # Apply pagination
        paginated_results = match_results["matches"][offset:offset+limit]
        
        return {
            "deal_id": str(deal_id),
            "results": paginated_results,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error getting goal matches for deal {deal_id}: {str(e)}")
        raise DealNotFoundError(f"Failed to get goal matches for deal: {str(e)}")

async def _find_matching_deals(
    self,
    goal_data: Dict[str, Any],
    max_results: int = 10,
    min_score: float = GOAL_MATCH_THRESHOLD
) -> List[Dict[str, Any]]:
    """Find deals matching a goal.
    
    Args:
        goal_data: Goal data dictionary
        max_results: Maximum number of results to return
        min_score: Minimum match score threshold
        
    Returns:
        List of matching deals with scores
    """
    try:
        # Extract goal details for filtering
        price_min = goal_data.get("price_min")
        price_max = goal_data.get("price_max")
        category = goal_data.get("category")
        keywords = goal_data.get("keywords") or []
        
        # Build initial filter parameters
        filter_params = {
            "status": DealStatus.ACTIVE.value,
            "limit": 50  # Get more deals to filter and score
        }
        
        # Add category filter if provided
        if category:
            filter_params["category"] = category
            
        # Add price range filters if provided
        if price_min is not None:
            filter_params["price_min"] = price_min
        if price_max is not None:
            filter_params["price_max"] = price_max
            
        # Get deals from repository
        deals = await self._repository.get_deals(**filter_params)
        
        # No deals found matching basic criteria
        if not deals:
            return []
            
        # Calculate match score for each deal
        matching_deals = []
        
        for deal in deals:
            # Convert deal to dictionary
            deal_data = {
                "id": deal.id,
                "title": deal.title,
                "description": deal.description,
                "price": deal.price,
                "original_price": deal.original_price,
                "category": deal.category,
                "seller_info": deal.seller_info,
                "deal_metadata": deal.deal_metadata
            }
            
            # Calculate match score
            match_result = await self._calculate_goal_match(deal_data, goal_data)
            
            # Check if meets threshold
            if match_result["score"] >= min_score:
                matching_deals.append({
                    "deal_id": deal.id,
                    "title": deal.title,
                    "price": str(deal.price),
                    "original_price": str(deal.original_price) if deal.original_price else None,
                    "url": deal.url,
                    "image_url": deal.image_url,
                    "category": deal.category,
                    "match_score": match_result["score"],
                    "match_reasons": match_result["reasons"]
                })
                
        # Sort by match score and limit results
        matching_deals.sort(key=lambda x: x["match_score"], reverse=True)
        return matching_deals[:max_results]
        
    except Exception as e:
        logger.error(f"Error finding matching deals: {str(e)}")
        return []

async def _calculate_goal_match(
    self,
    deal_data: Dict[str, Any],
    goal_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate match score between a deal and a goal.
    
    Args:
        deal_data: Deal data dictionary
        goal_data: Goal data dictionary
        
    Returns:
        Dictionary with match score and reasons
    """
    # Initialize score components
    scores = {}
    reasons = []
    
    # 1. Check price range (if specified)
    price_min = goal_data.get("price_min")
    price_max = goal_data.get("price_max")
    deal_price = float(deal_data.get("price", 0))
    
    if price_min is not None and price_max is not None:
        # Perfect score if within range, penalty if outside
        price_range = price_max - price_min
        if price_min <= deal_price <= price_max:
            scores["price_range"] = 1.0
            reasons.append(f"Price ${deal_price:.2f} is within your budget (${price_min:.2f}-${price_max:.2f})")
        elif price_min > 0 and deal_price < price_min:
            # Calculate how close it is to the range
            distance = (price_min - deal_price) / price_min
            scores["price_range"] = max(0, 1 - distance)
            reasons.append(f"Price ${deal_price:.2f} is below your minimum budget of ${price_min:.2f}")
        elif price_max > 0 and deal_price > price_max:
            # Calculate how close it is to the range
            distance = (deal_price - price_max) / price_max
            scores["price_range"] = max(0, 1 - distance)
            # Don't add as a reason if it's a negative
    
    # 2. Check discount (if original price available)
    deal_original_price = float(deal_data.get("original_price", 0))
    if deal_original_price > 0 and deal_price > 0 and deal_original_price > deal_price:
        discount_pct = (deal_original_price - deal_price) / deal_original_price * 100
        
        # Score based on discount percentage
        if discount_pct >= 50:
            scores["discount"] = 1.0
            reasons.append(f"Great discount of {discount_pct:.0f}% off")
        elif discount_pct >= 30:
            scores["discount"] = 0.8
            reasons.append(f"Good discount of {discount_pct:.0f}% off")
        elif discount_pct >= 15:
            scores["discount"] = 0.6
            reasons.append(f"Discount of {discount_pct:.0f}% off")
        else:
            scores["discount"] = 0.3
    
    # 3. Check category match
    goal_category = goal_data.get("category", "").lower()
    deal_category = deal_data.get("category", "").lower()
    
    if goal_category and deal_category:
        if goal_category == deal_category:
            scores["category"] = 1.0
            reasons.append(f"Exact category match: {deal_category}")
        elif goal_category in deal_category or deal_category in goal_category:
            scores["category"] = 0.7
            reasons.append(f"Related category: {deal_category}")
        else:
            scores["category"] = 0.0
    
    # 4. Check keyword matches
    goal_keywords = goal_data.get("keywords", [])
    goal_title = goal_data.get("title", "").lower()
    deal_title = deal_data.get("title", "").lower()
    deal_description = deal_data.get("description", "").lower()
    
    # Extract keywords from goal title if no keywords specified
    if not goal_keywords and goal_title:
        # Remove common words and split into keywords
        common_words = {"the", "a", "an", "and", "or", "but", "for", "nor", "on", "at", "to", "by", "from"}
        goal_keywords = [word for word in re.findall(r'\b\w+\b', goal_title.lower()) 
                        if word not in common_words and len(word) > 2]
    
    if goal_keywords:
        matched_keywords = []
        
        for keyword in goal_keywords:
            keyword = keyword.lower()
            if keyword in deal_title or keyword in deal_description:
                matched_keywords.append(keyword)
        
        keyword_score = len(matched_keywords) / len(goal_keywords) if goal_keywords else 0
        scores["keywords"] = keyword_score
        
        if matched_keywords:
            keywords_str = ", ".join(matched_keywords)
            reasons.append(f"Matches keywords: {keywords_str}")
    
    # 5. Calculate title similarity
    if goal_title and deal_title:
        # Count word overlap between titles
        goal_words = set(re.findall(r'\b\w+\b', goal_title.lower()))
        deal_words = set(re.findall(r'\b\w+\b', deal_title.lower()))
        
        if goal_words and deal_words:
            overlap = len(goal_words.intersection(deal_words))
            title_similarity = overlap / len(goal_words)
            scores["title_similarity"] = title_similarity
            
            if title_similarity >= 0.5:
                reasons.append("Title closely matches your goal")
    
    # Calculate final score with weighted components
    weights = {
        "price_range": 0.3,
        "discount": 0.2,
        "category": 0.2,
        "keywords": 0.2,
        "title_similarity": 0.1
    }
    
    final_score = 0.0
    total_weight = 0.0
    
    for component, score in scores.items():
        weight = weights.get(component, 0)
        final_score += score * weight
        total_weight += weight
    
    # Normalize score if we have any components
    if total_weight > 0:
        final_score = final_score / total_weight
    
    # Add match quality indicator
    if final_score >= 0.8:
        match_quality = MatchScore.EXCELLENT.value
    elif final_score >= 0.6:
        match_quality = MatchScore.GOOD.value
    elif final_score >= 0.4:
        match_quality = MatchScore.FAIR.value
    else:
        match_quality = MatchScore.POOR.value
    
    return {
        "score": final_score,
        "match_quality": match_quality,
        "reasons": reasons,
        "component_scores": scores
    }

async def _notify_goal_matches(
    self,
    goal_id: UUID,
    user_id: UUID,
    matches: List[Dict[str, Any]],
    goal_title: str
) -> None:
    """Notify user of new deal matches for their goal.
    
    Args:
        goal_id: The goal ID
        user_id: The user ID
        matches: List of matching deals
        goal_title: The goal title
    """
    try:
        if not matches:
            return
            
        # Get match count
        match_count = len(matches)
        
        # Create notification data
        notification_data = {
            "type": "goal_matches",
            "goal_id": str(goal_id),
            "goal_title": goal_title,
            "match_count": match_count,
            "matches": [{
                "deal_id": match["deal_id"], 
                "title": match["title"],
                "price": match["price"],
                "match_score": match["match_score"]
            } for match in matches[:3]]  # Include top 3 matches
        }
        
        # Send notification
        await self._notification_service.send_notification(
            user_id=user_id,
            notification_type="goal_matches",
            data=notification_data
        )
        
        logger.info(f"Notified user {user_id} of {match_count} new matches for goal {goal_id}")
        
    except Exception as e:
        logger.error(f"Error notifying user {user_id} of goal matches: {str(e)}")

async def _notify_deal_matches(
    self,
    deal_id: UUID,
    user_id: UUID,
    matches: List[Dict[str, Any]],
    deal_title: str
) -> None:
    """Notify user of a new deal matching their goals.
    
    Args:
        deal_id: The deal ID
        user_id: The user ID
        matches: List of matching goals
        deal_title: The deal title
    """
    try:
        if not matches:
            return
            
        # Get match count
        match_count = len(matches)
        
        # Create notification data
        notification_data = {
            "type": "deal_matches",
            "deal_id": str(deal_id),
            "deal_title": deal_title,
            "match_count": match_count,
            "matches": [{
                "goal_id": match["goal_id"], 
                "title": match["title"],
                "match_score": match["match_score"]
            } for match in matches[:3]]  # Include top 3 matches
        }
        
        # Send notification
        await self._notification_service.send_notification(
            user_id=user_id,
            notification_type="deal_matches",
            data=notification_data
        )
        
        logger.info(f"Notified user {user_id} of deal {deal_id} matching {match_count} goals")
        
    except Exception as e:
        logger.error(f"Error notifying user {user_id} of deal matches: {str(e)}")

async def match_with_goals(
    self,
    deal_id: UUID,
    user_id: Optional[UUID] = None,
    min_score: float = GOAL_MATCH_THRESHOLD
) -> Dict[str, Any]:
    """Match a deal with user goals.
    
    This is a wrapper around match_deal_to_goals for compatibility.
    
    Args:
        deal_id: The ID of the deal to match
        user_id: Optional user ID to restrict matching to
        min_score: Minimum match score threshold
        
    Returns:
        Dictionary with match results
        
    Raises:
        DealNotFoundError: If deal not found
    """
    try:
        # Check if deal exists
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Use existing match_deal_to_goals method
        match_results = await self.match_deal_to_goals(
            deal_id=deal_id,
            min_score=min_score,
            automatic_notify=True
        )
        
        # Filter by user_id if provided
        if user_id:
            # Filter matches to only those for the specified user
            filtered_matches = [
                match for match in match_results.get("matches", [])
                if match.get("user_id") == str(user_id)
            ]
            
            # Update the results with filtered matches
            match_results["matches"] = filtered_matches
            match_results["match_count"] = len(filtered_matches)
            
        return match_results
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error matching deal {deal_id} with goals: {str(e)}")
        raise DealNotFoundError(f"Failed to match deal with goals: {str(e)}")

async def get_matched_goals(
    self,
    deal_id: UUID,
    user_id: Optional[UUID] = None,
    limit: int = 10,
    offset: int = 0
) -> Dict[str, Any]:
    """Get goals that match a deal with pagination.
    
    This is a wrapper around get_goal_matches_for_deal for compatibility.
    
    Args:
        deal_id: The deal ID
        user_id: Optional user ID to filter results
        limit: Maximum number of goals to return
        offset: Number of goals to skip
        
    Returns:
        Dictionary with matched goals and pagination info
        
    Raises:
        DealNotFoundError: If deal not found
    """
    try:
        # Use existing get_goal_matches_for_deal method
        match_results = await self.get_goal_matches_for_deal(
            deal_id=deal_id,
            limit=limit if not user_id else 100,  # Get more if filtering by user
            offset=offset if not user_id else 0
        )
        
        # Filter by user_id if provided
        if user_id:
            # Filter matches to only those for the specified user
            all_matches = match_results.get("results", [])
            user_matches = [
                match for match in all_matches
                if match.get("user_id") == str(user_id)
            ]
            
            # Apply pagination after filtering
            total_user_matches = len(user_matches)
            paginated_matches = user_matches[offset:offset+limit]
            
            # Update the results with filtered and paginated matches
            match_results["results"] = paginated_matches
            match_results["total"] = total_user_matches
            match_results["has_more"] = (offset + limit) < total_user_matches
            
        return match_results
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error getting matched goals for deal {deal_id}: {str(e)}")
        raise DealNotFoundError(f"Failed to get matched goals: {str(e)}")

async def _matches_goal_criteria(
    self,
    deal: Any,
    goal: Any
) -> Tuple[bool, float, List[str]]:
    """Check if a deal matches goal criteria.
    
    Args:
        deal: Deal object or dictionary
        goal: Goal object or dictionary
        
    Returns:
        Tuple of (matches, score, reasons)
    """
    # Try the simplified legacy check first for quick rejection
    try:
        # Convert to dictionaries for consistency
        deal_dict = self._deal_to_dict(deal) if not isinstance(deal, dict) else deal
        
        # Handle both new-style and legacy goal formats
        if isinstance(goal, dict):
            goal_dict = goal
            constraints = goal.get("constraints", {})
            
            # Quick compatibility check using legacy approach
            # Check price range from constraints
            if "price_range" in constraints:
                price_range = constraints["price_range"]
                if "min" in price_range and deal_dict.get("price", 0) < Decimal(str(price_range["min"])):
                    return (False, 0.0, ["Price below minimum"])
                if "max" in price_range and deal_dict.get("price", 0) > Decimal(str(price_range["max"])):
                    return (False, 0.0, ["Price above maximum"])
                
            # Check keywords
            if "keywords" in constraints:
                keywords = constraints["keywords"]
                if keywords and not any(keyword.lower() in deal_dict.get("title", "").lower() for keyword in keywords):
                    return (False, 0.0, ["No keyword matches"])
                
            # Check categories
            if "categories" in constraints:
                categories = constraints["categories"]
                if categories and deal_dict.get("category") not in categories:
                    return (False, 0.0, ["Category mismatch"])
        else:
            # For goal objects
            goal_dict = {
                "id": getattr(goal, "id", None),
                "title": getattr(goal, "title", ""),
                "description": getattr(goal, "description", ""),
                "price_min": getattr(goal, "price_min", None),
                "price_max": getattr(goal, "price_max", None),
                "category": getattr(goal, "category", None),
                "keywords": getattr(goal, "keywords", [])
            }
    except Exception as e:
        logger.warning(f"Error in quick goal criteria check: {str(e)}")
        # Continue to more sophisticated check
    
    # Perform the more sophisticated check with detailed scoring
    try:
        # Calculate match score using the algorithm from _calculate_goal_match
        match_result = await self._calculate_goal_match(deal_dict, goal_dict)
        
        # Consider it a match if score is above threshold
        matches = match_result["score"] >= GOAL_MATCH_THRESHOLD
        
        return (matches, match_result["score"], match_result["reasons"])
    except Exception as e:
        logger.error(f"Error in detailed goal criteria check: {str(e)}")
        # Fall back to simple match
        return (True, 0.5, ["Match calculation error, using default score"])

def _deal_to_dict(self, deal) -> Dict[str, Any]:
    """Convert a deal object to dictionary.
    
    Args:
        deal: Deal object
        
    Returns:
        Dictionary representation of the deal
    """
    if isinstance(deal, dict):
        return deal
        
    result = {}
    
    # Get all attributes that are not callables or private
    for key in dir(deal):
        if not key.startswith('_') and not callable(getattr(deal, key)):
            value = getattr(deal, key)
            
            # Convert special types
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, Decimal):
                result[key] = str(value)
            else:
                result[key] = value
                
    return result 