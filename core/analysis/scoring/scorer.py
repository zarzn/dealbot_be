"""Enhanced deal scoring system."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
from uuid import UUID
from decimal import Decimal

from core.models.deal import Deal
from core.models.goal import Goal
from core.exceptions import DealScoreError
from core.utils.logger import get_logger
from core.utils.metrics import MetricsCollector

logger = get_logger(__name__)

class DealScorer:
    """Enhanced deal scoring system with ML capabilities."""
    
    def __init__(self):
        self.weights = {
            'price_competitiveness': 0.3,
            'historical_trend': 0.2,
            'market_position': 0.15,
            'seller_reliability': 0.15,
            'availability': 0.1,
            'seasonality': 0.1
        }
        
    async def calculate_comprehensive_score(
        self,
        deal: Deal,
        similar_deals: List[Dict[str, Any]],
        price_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate comprehensive deal score using multiple factors."""
        try:
            scores = {
                'price_competitiveness': await self._calculate_price_competitiveness(deal, similar_deals),
                'historical_trend': await self._analyze_price_trend(price_history),
                'market_position': await self._evaluate_market_position(deal, similar_deals),
                'seller_reliability': await self._assess_seller_reliability(deal),
                'availability': await self._check_availability_score(deal),
                'seasonality': await self._analyze_seasonality(price_history)
            }
            
            # Calculate weighted score
            final_score = sum(
                scores[key] * self.weights[key]
                for key in scores
            )
            
            confidence = await self._calculate_confidence(scores)
            
            return {
                'score': final_score,
                'confidence': confidence,
                'component_scores': scores,
                'analysis_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating deal score: {str(e)}")
            raise DealScoreError(f"Failed to calculate deal score: {str(e)}")
            
    async def _calculate_price_competitiveness(
        self,
        deal: Deal,
        similar_deals: List[Dict[str, Any]]
    ) -> float:
        """Calculate how competitive the deal price is compared to similar deals."""
        if not similar_deals:
            return 0.5  # Neutral score if no comparison available
            
        try:
            prices = [d['price'] for d in similar_deals if 'price' in d]
            if not prices:
                return 0.5
                
            avg_price = np.mean(prices)
            price_std = np.std(prices) if len(prices) > 1 else avg_price * 0.1
            
            # Calculate z-score of deal price
            z_score = (float(deal.price) - avg_price) / price_std if price_std > 0 else 0
            
            # Convert to 0-1 score (lower price is better)
            score = 1 - (1 / (1 + np.exp(-z_score)))
            
            return min(max(score, 0), 1)  # Ensure score is between 0 and 1
            
        except Exception as e:
            logger.error(f"Error calculating price competitiveness: {str(e)}")
            return 0.5
            
    async def _analyze_price_trend(
        self,
        price_history: List[Dict[str, Any]]
    ) -> float:
        """Analyze price trend to determine if current price is favorable."""
        if not price_history:
            return 0.5
            
        try:
            prices = [p['price'] for p in price_history]
            timestamps = [datetime.fromisoformat(p['timestamp']) for p in price_history]
            
            if len(prices) < 2:
                return 0.5
                
            # Calculate price trend
            price_changes = np.diff(prices)
            avg_change = np.mean(price_changes)
            
            # Convert to score (negative change is better)
            score = 1 - (1 / (1 + np.exp(-avg_change)))
            
            return min(max(score, 0), 1)
            
        except Exception as e:
            logger.error(f"Error analyzing price trend: {str(e)}")
            return 0.5
            
    async def _evaluate_market_position(
        self,
        deal: Deal,
        similar_deals: List[Dict[str, Any]]
    ) -> float:
        """Evaluate the deal's position in the market."""
        try:
            if not similar_deals:
                return 0.5
                
            better_deals = sum(
                1 for d in similar_deals
                if d.get('price', float('inf')) <= float(deal.price) and
                d.get('rating', 0) >= deal.rating
            )
            
            position_score = 1 - (better_deals / len(similar_deals))
            return min(max(position_score, 0), 1)
            
        except Exception as e:
            logger.error(f"Error evaluating market position: {str(e)}")
            return 0.5
            
    async def _assess_seller_reliability(self, deal: Deal) -> float:
        """Assess the reliability of the seller."""
        try:
            # Normalize seller rating to 0-1 scale
            rating = deal.seller_rating if hasattr(deal, 'seller_rating') else None
            if rating is None:
                return 0.5
                
            # Convert 5-star rating to 0-1 scale
            normalized_rating = rating / 5.0
            
            # Consider seller history if available
            history_score = deal.seller_history_score if hasattr(deal, 'seller_history_score') else 0.5
            
            # Combine scores with weights
            reliability_score = (normalized_rating * 0.7) + (history_score * 0.3)
            
            return min(max(reliability_score, 0), 1)
            
        except Exception as e:
            logger.error(f"Error assessing seller reliability: {str(e)}")
            return 0.5
            
    async def _check_availability_score(self, deal: Deal) -> float:
        """Calculate availability score based on stock level and shipping time."""
        try:
            # Convert stock level to score
            stock_level = deal.stock_level if hasattr(deal, 'stock_level') else None
            if stock_level is None:
                return 0.5
                
            # Higher stock level is better, but with diminishing returns
            stock_score = 1 - np.exp(-stock_level / 100)
            
            # Consider shipping time if available
            shipping_days = deal.shipping_days if hasattr(deal, 'shipping_days') else None
            if shipping_days is None:
                return stock_score
                
            # Convert shipping time to score (faster is better)
            shipping_score = 1 - (1 / (1 + np.exp(-shipping_days + 3)))
            
            # Combine scores
            availability_score = (stock_score * 0.6) + (shipping_score * 0.4)
            
            return min(max(availability_score, 0), 1)
            
        except Exception as e:
            logger.error(f"Error calculating availability score: {str(e)}")
            return 0.5
            
    async def _analyze_seasonality(
        self,
        price_history: List[Dict[str, Any]]
    ) -> float:
        """Analyze seasonal patterns in price history."""
        if not price_history or len(price_history) < 30:  # Need at least 30 days
            return 0.5
            
        try:
            prices = [p['price'] for p in price_history]
            timestamps = [datetime.fromisoformat(p['timestamp']) for p in price_history]
            
            # Check if current time is favorable based on historical patterns
            current_month = datetime.utcnow().month
            month_prices = [
                p for p, t in zip(prices, timestamps)
                if t.month == current_month
            ]
            
            if not month_prices:
                return 0.5
                
            current_price = prices[-1]
            month_avg = np.mean(month_prices)
            
            # Calculate how favorable current price is compared to seasonal average
            seasonal_score = 1 - (current_price / month_avg if month_avg > 0 else 1)
            
            return min(max(seasonal_score, 0), 1)
            
        except Exception as e:
            logger.error(f"Error analyzing seasonality: {str(e)}")
            return 0.5
            
    async def _calculate_confidence(self, scores: Dict[str, float]) -> float:
        """Calculate confidence level in the scoring."""
        try:
            # Check data availability
            data_availability = sum(
                1 for score in scores.values()
                if score != 0.5  # 0.5 indicates neutral/missing data
            ) / len(scores)
            
            # Calculate score consistency
            score_std = np.std(list(scores.values()))
            consistency = 1 - (score_std / 0.5)  # 0.5 is max possible std
            
            # Combine factors
            confidence = (data_availability * 0.7) + (consistency * 0.3)
            
            return min(max(confidence, 0), 1)
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {str(e)}")
            return 0.5 