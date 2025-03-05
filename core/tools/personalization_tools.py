"""Tools for personalization agent.

This module provides tools for preference learning, recommendation optimization,
notification priority management, and feedback processing.
"""

from typing import Dict, Any, List, Optional
from langchain_community.tools import BaseTool
from pydantic import BaseModel, Field
from datetime import datetime

class UserProfileInput(BaseModel):
    """Input model for user profile analysis"""
    user_id: str = Field(..., description="User identifier")
    interaction_history: Optional[List[Dict[str, Any]]] = Field(None, description="User interactions")
    current_goals: Optional[List[Dict[str, Any]]] = Field(None, description="Active user goals")

class RecommendationInput(BaseModel):
    """Input model for recommendation generation"""
    user_id: str = Field(..., description="User identifier")
    context: Dict[str, Any] = Field(..., description="Current context")
    max_recommendations: Optional[int] = Field(5, description="Maximum recommendations")

class PreferenceLearningTool(BaseTool):
    """Tool for learning user preferences"""
    name = "preference_learning"
    description = "Learn and update user preferences from interactions"
    args_schema = UserProfileInput

    def _run(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Run preference learning"""
        preferences = {
            "learned_preferences": self._analyze_preferences(user_id, kwargs),
            "preference_strength": self._calculate_preference_strength(user_id),
            "category_affinities": self._get_category_affinities(user_id),
            "price_sensitivity": self._analyze_price_sensitivity(user_id),
            "last_updated": datetime.utcnow().isoformat()
        }
        
        return preferences

    async def _arun(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Async run preference learning"""
        return self._run(user_id, **kwargs)

    def _analyze_preferences(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user preferences"""
        return {
            "categories": {
                "electronics": 0.8,
                "books": 0.3
            },
            "brands": {
                "samsung": 0.9,
                "apple": 0.7
            },
            "price_ranges": {
                "low": 0.2,
                "medium": 0.7,
                "high": 0.1
            },
            "confidence": 0.8
        }

    def _calculate_preference_strength(self, user_id: str) -> Dict[str, float]:
        """Calculate preference strength scores"""
        return {
            "brand_loyalty": 0.7,
            "price_sensitivity": 0.8,
            "quality_preference": 0.6,
            "deal_seeking": 0.9
        }

    def _get_category_affinities(self, user_id: str) -> List[Dict[str, Any]]:
        """Get category affinities"""
        return [
            {
                "category": "electronics",
                "affinity": 0.8,
                "confidence": 0.9
            },
            {
                "category": "books",
                "affinity": 0.3,
                "confidence": 0.7
            }
        ]

    def _analyze_price_sensitivity(self, user_id: str) -> Dict[str, Any]:
        """Analyze price sensitivity"""
        return {
            "overall_sensitivity": 0.8,
            "category_sensitivity": {
                "electronics": 0.9,
                "books": 0.5
            },
            "price_range_preference": {
                "low": 0.2,
                "medium": 0.7,
                "high": 0.1
            },
            "confidence": 0.8
        }

class RecommendationOptimizationTool(BaseTool):
    """Tool for optimizing recommendations"""
    name = "recommendation_optimization"
    description = "Optimize and personalize recommendations"
    args_schema = RecommendationInput

    def _run(self, user_id: str, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Run recommendation optimization"""
        recommendations = {
            "items": self._generate_recommendations(user_id, context),
            "explanation": self._generate_explanation(user_id),
            "metadata": {
                "optimization_factors": self._get_optimization_factors(user_id),
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
        return recommendations

    async def _arun(self, user_id: str, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Async run recommendation optimization"""
        return self._run(user_id, context, **kwargs)

    def _generate_recommendations(self, user_id: str, 
                                context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate personalized recommendations"""
        return [
            {
                "item_id": "rec_1",
                "title": "Recommended Product 1",
                "relevance_score": 0.9,
                "price": 99.99,
                "reasoning": ["price_match", "brand_preference"]
            }
        ]

    def _generate_explanation(self, user_id: str) -> Dict[str, Any]:
        """Generate recommendation explanations"""
        return {
            "factors": [
                "Based on your previous purchases",
                "Matches your price range",
                "Popular in your preferred category"
            ],
            "confidence": 0.8
        }

    def _get_optimization_factors(self, user_id: str) -> Dict[str, Any]:
        """Get recommendation optimization factors"""
        return {
            "user_preferences": 0.4,
            "current_context": 0.3,
            "market_trends": 0.2,
            "similar_users": 0.1
        }

class NotificationPriorityTool(BaseTool):
    """Tool for managing notification priorities"""
    name = "notification_priority"
    description = "Manage and optimize notification priorities"

    def _run(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Run notification priority management"""
        priority = {
            "priority_score": self._calculate_priority(notification),
            "delivery_schedule": self._optimize_delivery_time(notification),
            "grouping": self._check_grouping(notification),
            "metadata": {
                "priority_factors": self._get_priority_factors(notification),
                "calculated_at": datetime.utcnow().isoformat()
            }
        }
        
        return priority

    async def _arun(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Async run notification priority management"""
        return self._run(notification)

    def _calculate_priority(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate notification priority"""
        return {
            "score": 0.8,
            "urgency": "high",
            "user_relevance": 0.9,
            "context_relevance": 0.7
        }

    def _optimize_delivery_time(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize notification delivery time"""
        return {
            "suggested_time": datetime.utcnow().isoformat(),
            "time_window": {
                "start": "09:00",
                "end": "21:00"
            },
            "user_timezone": "UTC"
        }

    def _check_grouping(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Check notification grouping"""
        return {
            "should_group": True,
            "group_key": "price_alerts",
            "group_size": 3,
            "group_window": "1h"
        }

    def _get_priority_factors(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Get priority calculation factors"""
        return {
            "deal_quality": 0.3,
            "user_preferences": 0.3,
            "time_sensitivity": 0.2,
            "context_relevance": 0.2
        }

class FeedbackProcessingTool(BaseTool):
    """Tool for processing user feedback"""
    name = "feedback_processing"
    description = "Process and analyze user feedback"

    def _run(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Run feedback processing"""
        analysis = {
            "processed_feedback": self._process_feedback(feedback),
            "preference_updates": self._extract_preferences(feedback),
            "improvement_suggestions": self._generate_improvements(feedback),
            "metadata": {
                "feedback_type": feedback.get("type", "general"),
                "processed_at": datetime.utcnow().isoformat()
            }
        }
        
        return analysis

    async def _arun(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Async run feedback processing"""
        return self._run(feedback)

    def _process_feedback(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw feedback"""
        return {
            "sentiment": "positive",
            "categories": ["price", "relevance"],
            "action_required": False,
            "confidence": 0.8
        }

    def _extract_preferences(self, feedback: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract preference updates from feedback"""
        return [
            {
                "type": "price_preference",
                "update": {"max_price": 1000},
                "confidence": 0.9
            },
            {
                "type": "category_preference",
                "update": {"category": "electronics"},
                "confidence": 0.8
            }
        ]

    def _generate_improvements(self, feedback: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate improvement suggestions"""
        return [
            {
                "area": "recommendations",
                "suggestion": "Adjust price range",
                "priority": "high"
            },
            {
                "area": "notifications",
                "suggestion": "Reduce frequency",
                "priority": "medium"
            }
        ] 