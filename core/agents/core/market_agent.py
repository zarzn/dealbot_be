"""Market Intelligence Agent.

This agent is responsible for market search, price analysis,
deal validation, and search optimization.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from pydantic import BaseModel

from core.agents.base.base_agent import BaseAgent, AgentRequest, AgentResponse
from core.agents.utils.llm_manager import LLMManager, LLMRequest
from core.agents.config.agent_config import PriorityLevel, LLMProvider
from core.utils.logger import get_logger

logger = get_logger(__name__)

class PriceHistory(BaseModel):
    """Model for price history data"""
    timestamps: List[datetime]
    prices: List[float]
    source: str

class MarketTrend(BaseModel):
    """Model for market trend analysis"""
    trend: str  # "up", "down", "stable"
    confidence: float
    prediction: Optional[float]
    factors: List[str]

class MarketAgent(BaseAgent):
    """Agent for market intelligence and analysis"""

    def __init__(self):
        super().__init__("market_agent")
        self.llm_manager = None

    async def _setup_agent(self):
        """Setup market agent"""
        self.llm_manager = LLMManager()
        await self.llm_manager.initialize()

    async def _process_request(self, request: AgentRequest) -> Dict[str, Any]:
        """Process market-related request"""
        action = request.payload.get("action")
        
        if action == "analyze_price":
            return await self._analyze_price(request)
        elif action == "validate_market":
            return await self._validate_market(request)
        elif action == "optimize_search":
            return await self._optimize_search(request)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _analyze_price(self, request: AgentRequest) -> Dict[str, Any]:
        """Analyze price history and trends"""
        price_history = request.payload.get("price_history")
        if not price_history:
            raise ValueError("Price history is required")

        # Convert to PriceHistory model
        history = PriceHistory(**price_history)
        
        # Analyze trends
        trend_analysis = self._analyze_price_trends(history)
        
        # Get market context
        market_context = await self._get_market_context(
            history.source,
            trend_analysis
        )
        
        return {
            "trend_analysis": trend_analysis.dict(),
            "market_context": market_context,
            "deal_quality_score": self._calculate_deal_quality(
                trend_analysis,
                market_context
            )
        }

    async def _validate_market(self, request: AgentRequest) -> Dict[str, Any]:
        """Validate market source reliability"""
        source = request.payload.get("source")
        if not source:
            raise ValueError("Market source is required")

        # Check source reliability
        reliability_score = await self._check_source_reliability(source)
        
        # Get recent performance metrics
        performance_metrics = await self._get_source_performance(source)
        
        return {
            "is_reliable": reliability_score >= 0.7,
            "reliability_score": reliability_score,
            "performance_metrics": performance_metrics,
            "recommendations": self._generate_source_recommendations(
                reliability_score,
                performance_metrics
            )
        }

    async def _optimize_search(self, request: AgentRequest) -> Dict[str, Any]:
        """Optimize search parameters based on market data"""
        search_params = request.payload.get("search_params")
        if not search_params:
            raise ValueError("Search parameters are required")

        # Analyze current market conditions
        market_conditions = await self._analyze_market_conditions(
            search_params
        )
        
        # Optimize parameters
        optimized_params = self._optimize_parameters(
            search_params,
            market_conditions
        )
        
        return {
            "optimized_params": optimized_params,
            "market_conditions": market_conditions,
            "optimization_score": self._calculate_optimization_score(
                search_params,
                optimized_params
            )
        }

    def _analyze_price_trends(self, history: PriceHistory) -> MarketTrend:
        """Analyze price history to detect trends"""
        if len(history.prices) < 2:
            return MarketTrend(
                trend="unknown",
                confidence=0.0,
                prediction=None,
                factors=["Insufficient price history"]
            )

        # Convert to pandas for analysis
        df = pd.DataFrame({
            'timestamp': history.timestamps,
            'price': history.prices
        })
        
        # Calculate basic statistics
        mean_price = df['price'].mean()
        std_price = df['price'].std()
        current_price = df['price'].iloc[-1]
        
        # Calculate trend
        price_change = (
            df['price'].iloc[-1] - df['price'].iloc[0]
        ) / df['price'].iloc[0]
        
        # Determine trend direction
        if price_change > 0.05:  # 5% threshold
            trend = "up"
        elif price_change < -0.05:
            trend = "down"
        else:
            trend = "stable"

        # Calculate confidence based on data quality
        confidence = self._calculate_trend_confidence(df)
        
        # Predict future price
        prediction = self._predict_future_price(df)
        
        # Identify contributing factors
        factors = self._identify_price_factors(df, mean_price, std_price)
        
        return MarketTrend(
            trend=trend,
            confidence=confidence,
            prediction=prediction,
            factors=factors
        )

    async def _get_market_context(
        self,
        source: str,
        trend: MarketTrend
    ) -> Dict[str, Any]:
        """Get broader market context using LLM"""
        prompt = self._generate_market_context_prompt(source, trend)
        
        response = await self.llm_manager.generate(
            LLMRequest(
                prompt=prompt,
                temperature=0.7  # Higher temperature for more diverse insights
            )
        )
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("Failed to parse market context response")
            return {
                "market_factors": [],
                "confidence": 0.0
            }

    def _calculate_deal_quality(
        self,
        trend: MarketTrend,
        context: Dict[str, Any]
    ) -> float:
        """Calculate overall deal quality score"""
        score = 0.0
        
        # Trend-based scoring
        if trend.trend == "down":
            score += 0.3  # Price dropping is good for buyers
        elif trend.trend == "stable":
            score += 0.2
        
        # Confidence impact
        score += trend.confidence * 0.3
        
        # Market context impact
        context_confidence = context.get("confidence", 0.0)
        score += context_confidence * 0.2
        
        # Prediction impact
        if trend.prediction and trend.prediction > 0:
            score += 0.2  # Positive future prediction
            
        return min(score, 1.0)

    async def _check_source_reliability(self, source: str) -> float:
        """Check reliability of market source"""
        # This would typically check against a database of known sources
        # For MVP, we'll use a simple scoring system
        reliability_factors = {
            "amazon": 0.9,
            "walmart": 0.85,
            "ebay": 0.75,
            "unknown": 0.5
        }
        
        return reliability_factors.get(source.lower(), 0.5)

    async def _get_source_performance(self, source: str) -> Dict[str, Any]:
        """Get performance metrics for market source"""
        # This would typically fetch real metrics from monitoring system
        # For MVP, return placeholder metrics
        return {
            "availability": 0.99,
            "response_time": 0.5,
            "error_rate": 0.01,
            "data_freshness": 0.95
        }

    def _generate_source_recommendations(
        self,
        reliability: float,
        performance: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations for market source usage"""
        recommendations = []
        
        if reliability < 0.7:
            recommendations.append(
                "Consider using more reliable primary sources"
            )
        if performance["error_rate"] > 0.05:
            recommendations.append(
                "Implement additional error handling for this source"
            )
        if performance["data_freshness"] < 0.9:
            recommendations.append(
                "Increase data refresh frequency"
            )
            
        return recommendations

    async def _analyze_market_conditions(
        self,
        search_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze current market conditions"""
        # This would typically involve real-time market analysis
        # For MVP, return basic analysis
        return {
            "market_activity": "high",
            "competition_level": "medium",
            "price_volatility": "low",
            "best_search_times": [
                "morning",
                "evening"
            ]
        }

    def _optimize_parameters(
        self,
        params: Dict[str, Any],
        conditions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize search parameters based on market conditions"""
        optimized = params.copy()
        
        # Adjust search frequency
        if conditions["market_activity"] == "high":
            optimized["refresh_interval"] = 300  # 5 minutes
        else:
            optimized["refresh_interval"] = 900  # 15 minutes
            
        # Adjust price thresholds
        if conditions["price_volatility"] == "high":
            optimized["price_threshold_buffer"] = 0.1  # 10%
        else:
            optimized["price_threshold_buffer"] = 0.05  # 5%
            
        return optimized

    def _calculate_optimization_score(
        self,
        original: Dict[str, Any],
        optimized: Dict[str, Any]
    ) -> float:
        """Calculate optimization improvement score"""
        improvements = 0
        total_params = len(original)
        
        for key in original:
            if key in optimized and original[key] != optimized[key]:
                improvements += 1
                
        return improvements / total_params

    def _calculate_trend_confidence(self, df: pd.DataFrame) -> float:
        """Calculate confidence in trend analysis"""
        # More data points increase confidence
        data_points_score = min(len(df) / 100, 0.5)
        
        # Less variance increases confidence
        variance_score = 0.5 * (1 - min(df['price'].std() / df['price'].mean(), 1))
        
        return data_points_score + variance_score

    def _predict_future_price(self, df: pd.DataFrame) -> Optional[float]:
        """Simple price prediction"""
        if len(df) < 3:
            return None
            
        # Simple linear extrapolation
        last_prices = df['price'].tail(3)
        avg_change = (last_prices.iloc[-1] - last_prices.iloc[0]) / 2
        
        return last_prices.iloc[-1] + avg_change

    def _identify_price_factors(
        self,
        df: pd.DataFrame,
        mean_price: float,
        std_price: float
    ) -> List[str]:
        """Identify factors affecting price"""
        factors = []
        
        # Volatility check
        if std_price / mean_price > 0.1:
            factors.append("High price volatility")
            
        # Trend strength
        price_change = (
            df['price'].iloc[-1] - df['price'].iloc[0]
        ) / df['price'].iloc[0]
        if abs(price_change) > 0.1:
            factors.append(
                f"Strong {'upward' if price_change > 0 else 'downward'} trend"
            )
            
        # Recent stability
        recent_std = df['price'].tail(min(len(df), 5)).std()
        if recent_std < std_price / 2:
            factors.append("Recent price stabilization")
            
        return factors

    def _generate_market_context_prompt(
        self,
        source: str,
        trend: MarketTrend
    ) -> str:
        """Generate prompt for market context analysis"""
        return f"""Analyze the market context for the following scenario:

Source: {source}
Price Trend: {trend.trend}
Confidence: {trend.confidence}
Prediction: {trend.prediction if trend.prediction else 'Unknown'}

Please provide a JSON response with the following structure:
{{
    "market_factors": [
        "list of relevant market factors"
    ],
    "confidence": float (0-1)
}}

Consider factors like seasonality, competition, and market conditions.""" 