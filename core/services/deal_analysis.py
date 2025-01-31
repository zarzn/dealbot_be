"""Deal analysis service module.

This module provides comprehensive deal analysis functionality for the AI Agentic Deals System,
including price analysis, historical data analysis, market analysis, and AI-driven scoring.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import IsolationForest

from ..models.deal import Deal
from ..models.goal import Goal
from ..utils.redis import get_redis_client
from ..utils.logger import get_logger
from ..utils.metrics import MetricsCollector
from ..exceptions import (
    ValidationError,
    DealAnalysisError,
    DataQualityError,
    ModelError
)
from ..config import settings

logger = get_logger(__name__)

@dataclass
class AnalysisResult:
    """Data class for analysis results."""
    deal_id: str
    score: float
    metrics: Dict[str, Dict[str, float]]
    analysis_timestamp: str
    confidence: float
    anomaly_score: float
    recommendations: List[str]

class DealAnalysisService:
    """Service for analyzing deals using advanced analytics and AI."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.scaler = MinMaxScaler()
        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42
        )

    async def analyze_deal(
        self,
        deal: Deal,
        goal: Goal,
        similar_deals: Optional[List[Dict[str, Any]]] = None
    ) -> AnalysisResult:
        """
        Analyze a deal to determine its quality and value using advanced analytics.

        Args:
            deal: Deal to analyze
            goal: Associated goal
            similar_deals: Optional list of similar deals for comparison

        Returns:
            AnalysisResult containing comprehensive analysis

        Raises:
            DealAnalysisError: If analysis fails
            DataQualityError: If data quality is insufficient
            ValidationError: If input validation fails
        """
        try:
            # Validate inputs
            if not deal or not goal:
                raise ValidationError("Deal and goal are required")

            # Get price history with error handling
            try:
                price_history = pd.DataFrame(deal.price_history)
                if not price_history.empty:
                    price_history['timestamp'] = pd.to_datetime(price_history['timestamp'])
                    price_history = price_history.sort_values('timestamp')
            except Exception as e:
                logger.error(f"Error processing price history: {str(e)}", exc_info=True)
                raise DataQualityError("Invalid price history data")

            # Get similar deals with retry logic
            if not similar_deals:
                similar_deals = await self._get_similar_deals_with_retry(deal)

            # Calculate metrics with confidence scores
            metrics, confidence = await self._calculate_metrics_with_confidence(
                deal,
                price_history,
                similar_deals,
                goal
            )

            # Detect anomalies
            anomaly_score = await self._detect_anomalies(deal, price_history, similar_deals)

            # Generate AI-driven recommendations
            recommendations = await self._generate_recommendations(
                deal,
                metrics,
                anomaly_score,
                goal
            )

            # Calculate overall score with confidence weighting
            score = self._calculate_overall_score(metrics, confidence)
            
            # Create analysis result
            result = AnalysisResult(
                deal_id=deal.id,
                score=score,
                metrics=metrics,
                analysis_timestamp=datetime.utcnow().isoformat(),
                confidence=confidence,
                anomaly_score=anomaly_score,
                recommendations=recommendations
            )

            # Cache analysis results
            await self._cache_analysis(deal.id, result.__dict__)

            # Track metrics
            MetricsCollector.track_deal_analysis(
                deal_id=deal.id,
                score=score,
                confidence=confidence,
                anomaly_score=anomaly_score
            )

            return result

        except (ValidationError, DataQualityError) as e:
            logger.warning(f"Analysis validation error: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Deal analysis error: {str(e)}", exc_info=True)
            raise DealAnalysisError(f"Failed to analyze deal: {str(e)}")

    async def _calculate_metrics_with_confidence(
        self,
        deal: Deal,
        price_history: pd.DataFrame,
        similar_deals: List[Dict[str, Any]],
        goal: Goal
    ) -> Tuple[Dict[str, Dict[str, float]], float]:
        """Calculate all metrics with confidence scores."""
        try:
            metrics = {
                "price_metrics": await self._analyze_price(deal, price_history, similar_deals),
                "historical_metrics": await self._analyze_historical_data(deal, price_history),
                "market_metrics": await self._analyze_market_data(deal, similar_deals),
                "goal_metrics": self._analyze_goal_fit(deal, goal)
            }

            # Calculate confidence based on data quality
            confidence_scores = {
                "price_data": 1.0 if not price_history.empty else 0.5,
                "similar_deals": min(len(similar_deals) / 10, 1.0) if similar_deals else 0.0,
                "market_data": 1.0 if deal.metadata.get("seller_rating") else 0.5,
                "goal_data": 1.0 if goal.criteria else 0.5
            }

            return metrics, np.mean(list(confidence_scores.values()))

        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}", exc_info=True)
            raise DealAnalysisError(f"Failed to calculate metrics: {str(e)}")

    async def _analyze_price(
        self,
        deal: Deal,
        price_history: pd.DataFrame,
        similar_deals: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Analyze price-related metrics with advanced analytics."""
        try:
            current_price = deal.price
            metrics = {
                "current_price": current_price,
                "price_volatility": 0.0,
                "price_trend": 0.0,
                "market_position": 0.0,
                "seasonality_score": 0.0,
                "price_momentum": 0.0
            }

            if not price_history.empty:
                # Calculate advanced price metrics
                prices = price_history['price'].values
                
                # Volatility using exponential weighted std
                if len(prices) > 1:
                    metrics["price_volatility"] = (
                        pd.Series(prices).ewm(span=7).std().iloc[-1] /
                        pd.Series(prices).ewm(span=7).mean().iloc[-1]
                    )

                # Price trend using linear regression
                if len(prices) > 2:
                    x = np.arange(len(prices)).reshape(-1, 1)
                    y = prices.reshape(-1, 1)
                    from sklearn.linear_model import LinearRegression
                    reg = LinearRegression().fit(x, y)
                    metrics["price_trend"] = reg.coef_[0][0]

                # Price momentum using ROC
                if len(prices) > 1:
                    momentum = (prices[-1] - prices[0]) / prices[0]
                    metrics["price_momentum"] = momentum

                # Seasonality detection
                if len(prices) > 14:
                    from statsmodels.tsa.seasonal import seasonal_decompose
                    try:
                        decomposition = seasonal_decompose(
                            prices,
                            period=7,
                            extrapolate_trend='freq'
                        )
                        metrics["seasonality_score"] = np.std(decomposition.seasonal)
                    except Exception as e:
                        logger.warning(f"Seasonality analysis failed: {str(e)}")

            # Market position analysis
            if similar_deals:
                similar_prices = [d["price"] for d in similar_deals]
                avg_price = np.mean(similar_prices)
                metrics["market_position"] = (avg_price - current_price) / avg_price

                # Calculate percentile rank
                metrics["price_percentile"] = (
                    sum(1 for p in similar_prices if p > current_price) /
                    len(similar_prices)
                )

            return metrics

        except Exception as e:
            logger.error(f"Error in price analysis: {str(e)}", exc_info=True)
            raise DealAnalysisError(f"Failed to analyze price: {str(e)}")

    async def _analyze_historical_data(
        self,
        deal: Deal,
        price_history: pd.DataFrame
    ) -> Dict[str, float]:
        """Analyze historical price data with advanced metrics."""
        try:
            metrics = {
                "price_stability": 0.0,
                "days_at_current_price": 0,
                "historical_low": deal.price,
                "historical_high": deal.price,
                "price_range_position": 0.5,
                "trend_strength": 0.0,
                "volatility_trend": 0.0
            }

            if not price_history.empty:
                prices = price_history['price'].values
                metrics.update({
                    "historical_low": float(np.min(prices)),
                    "historical_high": float(np.max(prices)),
                })

                if len(prices) > 1:
                    # Calculate days at current price
                    last_change = price_history[
                        price_history['price'] != deal.price
                    ]['timestamp'].max()
                    if pd.notna(last_change):
                        days_at_price = (
                            datetime.utcnow() - last_change.to_pydatetime()
                        ).days
                        metrics["days_at_current_price"] = days_at_price

                    # Price stability using various metrics
                    price_changes = price_history['price'].pct_change().abs()
                    metrics["price_stability"] = 1 - (
                        price_changes.ewm(span=7).mean().iloc[-1]
                        if not price_changes.empty else 0
                    )

                    # Position in historical range
                    price_range = metrics["historical_high"] - metrics["historical_low"]
                    if price_range > 0:
                        metrics["price_range_position"] = (
                            deal.price - metrics["historical_low"]
                        ) / price_range

                    # Trend strength using R-squared
                    if len(prices) > 2:
                        x = np.arange(len(prices)).reshape(-1, 1)
                        y = prices.reshape(-1, 1)
                        from sklearn.linear_model import LinearRegression
                        reg = LinearRegression().fit(x, y)
                        metrics["trend_strength"] = reg.score(x, y)

                    # Volatility trend
                    if len(prices) > 7:
                        rolling_vol = pd.Series(prices).rolling(7).std()
                        metrics["volatility_trend"] = (
                            rolling_vol.iloc[-1] - rolling_vol.iloc[6]
                        ) / rolling_vol.iloc[6]

            return metrics

        except Exception as e:
            logger.error(f"Error in historical analysis: {str(e)}", exc_info=True)
            raise DealAnalysisError(f"Failed to analyze historical data: {str(e)}")

    async def _analyze_market_data(
        self,
        deal: Deal,
        similar_deals: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Analyze market-related metrics with competition analysis."""
        try:
            metrics = {
                "competition_score": 0.0,
                "availability_score": 1.0 if deal.is_available else 0.0,
                "seller_rating": float(deal.metadata.get("seller_rating", 0.0)),
                "market_share": 0.0,
                "price_competitiveness": 0.0,
                "market_momentum": 0.0
            }

            if similar_deals:
                # Enhanced competition analysis
                better_deals = sum(1 for d in similar_deals if d["price"] < deal.price)
                metrics["competition_score"] = 1 - (better_deals / len(similar_deals))

                # Market share analysis
                seller_deals = sum(1 for d in similar_deals if d.get("seller") == deal.seller)
                metrics["market_share"] = seller_deals / len(similar_deals)

                # Price competitiveness
                similar_prices = [d["price"] for d in similar_deals]
                avg_price = np.mean(similar_prices)
                std_price = np.std(similar_prices)
                if std_price > 0:
                    z_score = (deal.price - avg_price) / std_price
                    metrics["price_competitiveness"] = 1 / (1 + np.exp(z_score))

                # Market momentum
                if all("created_at" in d for d in similar_deals):
                    recent_deals = [
                        d for d in similar_deals
                        if (datetime.utcnow() - d["created_at"]).days <= 7
                    ]
                    older_deals = [
                        d for d in similar_deals
                        if (datetime.utcnow() - d["created_at"]).days > 7
                    ]
                    if recent_deals and older_deals:
                        recent_avg = np.mean([d["price"] for d in recent_deals])
                        older_avg = np.mean([d["price"] for d in older_deals])
                        metrics["market_momentum"] = (recent_avg - older_avg) / older_avg

            return metrics

        except Exception as e:
            logger.error(f"Error in market analysis: {str(e)}", exc_info=True)
            raise DealAnalysisError(f"Failed to analyze market data: {str(e)}")

    def _analyze_goal_fit(self, deal: Deal, goal: Goal) -> Dict[str, float]:
        """Analyze how well the deal fits the goal criteria with semantic matching."""
        try:
            metrics = {
                "price_match": 0.0,
                "criteria_match": 0.0,
                "urgency_score": 0.0,
                "feature_match": 0.0,
                "brand_match": 0.0
            }

            # Enhanced price match calculation
            if goal.max_price:
                price_range = goal.max_price - (goal.min_price or 0)
                if price_range > 0:
                    price_distance = max(0, deal.price - (goal.min_price or 0))
                    metrics["price_match"] = 1 - (price_distance / price_range)
                    # Apply exponential penalty for prices above max_price
                    if deal.price > goal.max_price:
                        overage = (deal.price - goal.max_price) / goal.max_price
                        metrics["price_match"] *= np.exp(-overage)

            # Enhanced criteria matching using semantic similarity
            if goal.criteria:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                
                vectorizer = TfidfVectorizer()
                goal_text = " ".join(goal.criteria)
                deal_text = f"{deal.title} {deal.description}"
                
                try:
                    tfidf_matrix = vectorizer.fit_transform([goal_text, deal_text])
                    metrics["criteria_match"] = float(
                        cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
                    )
                except Exception as e:
                    logger.warning(f"Semantic matching failed: {str(e)}")
                    # Fallback to simple matching
                    matched_criteria = sum(
                        1 for c in goal.criteria
                        if c.lower() in deal.title.lower() or
                        c.lower() in deal.description.lower()
                    )
                    metrics["criteria_match"] = matched_criteria / len(goal.criteria)

            # Calculate urgency score with deadline proximity
            if goal.deadline:
                days_left = (goal.deadline - datetime.utcnow()).days
                metrics["urgency_score"] = 1 - (max(0, min(days_left, 30)) / 30)
                # Add exponential urgency for last few days
                if days_left < 7:
                    metrics["urgency_score"] = 1 - (np.exp(-max(0, days_left)) / np.exp(0))

            # Feature matching
            if goal.features and deal.metadata.get("features"):
                goal_features = set(goal.features)
                deal_features = set(deal.metadata["features"])
                if goal_features:
                    metrics["feature_match"] = len(
                        goal_features.intersection(deal_features)
                    ) / len(goal_features)

            # Brand matching
            if goal.preferred_brands and deal.metadata.get("brand"):
                metrics["brand_match"] = float(
                    deal.metadata["brand"] in goal.preferred_brands
                )

            return metrics

        except Exception as e:
            logger.error(f"Error in goal fit analysis: {str(e)}", exc_info=True)
            raise DealAnalysisError(f"Failed to analyze goal fit: {str(e)}")

    def _calculate_overall_score(
        self,
        metrics: Dict[str, Dict[str, float]],
        confidence: float
    ) -> float:
        """Calculate overall deal score with dynamic weighting."""
        try:
            # Base weights
            weights = {
                "price_metrics": 0.35,
                "historical_metrics": 0.20,
                "market_metrics": 0.25,
                "goal_metrics": 0.20
            }

            # Adjust weights based on confidence
            if confidence < 0.5:
                # Increase weight of more reliable metrics
                weights["goal_metrics"] += 0.1
                weights["price_metrics"] += 0.1
                weights["market_metrics"] -= 0.1
                weights["historical_metrics"] -= 0.1

            # Calculate weighted score
            score = 0.0
            for category, category_metrics in metrics.items():
                # Filter out non-numeric values
                numeric_metrics = {
                    k: v for k, v in category_metrics.items()
                    if isinstance(v, (int, float))
                }
                if numeric_metrics:
                    category_score = np.mean(list(numeric_metrics.values()))
                    score += category_score * weights[category]

            # Apply confidence adjustment
            score = score * (0.5 + 0.5 * confidence)

            return float(min(max(score, 0.0), 1.0))

        except Exception as e:
            logger.error(f"Error calculating overall score: {str(e)}", exc_info=True)
            raise DealAnalysisError(f"Failed to calculate overall score: {str(e)}")

    async def _get_similar_deals_with_retry(
        self,
        deal: Deal,
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """Get similar deals with retry logic."""
        for attempt in range(max_retries):
            try:
                similar = await self.session.execute(
                    select(Deal).where(
                        and_(
                            Deal.market_type == deal.market_type,
                            Deal.id != deal.id,
                            Deal.created_at >= datetime.utcnow() - timedelta(days=30),
                            Deal.is_active == True
                        )
                    ).order_by(func.random()).limit(10)
                )
                return [d.__dict__ for d in similar.scalars().all()]
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to get similar deals after {max_retries} attempts: {str(e)}",
                        exc_info=True
                    )
                    raise
                await asyncio.sleep(1 * (attempt + 1))

    async def _detect_anomalies(
        self,
        deal: Deal,
        price_history: pd.DataFrame,
        similar_deals: List[Dict[str, Any]]
    ) -> float:
        """Detect price anomalies using isolation forest."""
        try:
            if price_history.empty or not similar_deals:
                return 0.0

            # Prepare features for anomaly detection
            features = []
            
            # Price features
            current_price = deal.price
            similar_prices = [d["price"] for d in similar_deals]
            avg_price = np.mean(similar_prices)
            std_price = np.std(similar_prices)
            
            features.extend([
                current_price,
                current_price / avg_price if avg_price > 0 else 1.0,
                (current_price - avg_price) / std_price if std_price > 0 else 0.0
            ])
            
            # Historical features
            if len(price_history) > 1:
                price_changes = price_history['price'].pct_change().dropna()
                features.extend([
                    price_changes.mean(),
                    price_changes.std(),
                    len(price_changes)
                ])
            
            # Reshape and scale features
            X = np.array(features).reshape(1, -1)
            X_scaled = self.scaler.fit_transform(X)
            
            # Detect anomalies
            anomaly_scores = self.anomaly_detector.fit_predict(X_scaled)
            
            # Convert to probability-like score
            return float(1 / (1 + np.exp(-anomaly_scores[0])))

        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}", exc_info=True)
            return 0.0

    async def _generate_recommendations(
        self,
        deal: Deal,
        metrics: Dict[str, Dict[str, float]],
        anomaly_score: float,
        goal: Goal
    ) -> List[str]:
        """Generate AI-driven recommendations based on analysis."""
        try:
            recommendations = []

            # Price-based recommendations
            price_metrics = metrics["price_metrics"]
            if price_metrics["market_position"] < -0.2:
                recommendations.append(
                    "Price is significantly above market average. Consider waiting for a better deal."
                )
            elif price_metrics["price_trend"] < -0.05:
                recommendations.append(
                    "Price is showing a downward trend. May continue to decrease."
                )

            # Anomaly-based recommendations
            if anomaly_score > 0.7:
                recommendations.append(
                    "Deal shows unusual characteristics. Verify details carefully."
                )

            # Goal-based recommendations
            goal_metrics = metrics["goal_metrics"]
            if goal_metrics["price_match"] < 0.5:
                recommendations.append(
                    "Price is not optimal for your goal. Consider alternative options."
                )
            if goal_metrics["criteria_match"] < 0.6:
                recommendations.append(
                    "Deal may not fully match your criteria. Review specifications carefully."
                )

            # Market-based recommendations
            market_metrics = metrics["market_metrics"]
            if market_metrics["competition_score"] < 0.3:
                recommendations.append(
                    "Multiple better deals available. Compare alternatives."
                )

            # Urgency recommendations
            if goal.deadline:
                days_left = (goal.deadline - datetime.utcnow()).days
                if days_left < 7:
                    recommendations.append(
                        f"Goal deadline approaching ({days_left} days left). "
                        "Consider acting soon if deal meets requirements."
                    )

            return recommendations[:5]  # Limit to top 5 recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}", exc_info=True)
            return ["Unable to generate recommendations due to an error."]

    async def _cache_analysis(
        self,
        deal_id: str,
        analysis_data: Dict[str, Any]
    ) -> None:
        """Cache the analysis results with error handling."""
        try:
            redis = await get_redis_client()
            cache_key = f"deal_analysis:{deal_id}"
            
            # Convert numpy types to Python natives
            cleaned_data = self._clean_data_for_cache(analysis_data)
            
            await redis.set(
                cache_key,
                cleaned_data,
                ex=settings.DEAL_ANALYSIS_CACHE_TTL
            )
        except Exception as e:
            logger.error(f"Error caching analysis: {str(e)}", exc_info=True)
            # Don't raise - caching failure shouldn't fail the analysis

    def _clean_data_for_cache(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean data for caching by converting numpy types."""
        if isinstance(data, dict):
            return {
                k: self._clean_data_for_cache(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._clean_data_for_cache(v) for v in data]
        elif isinstance(data, (np.int_, np.intc, np.intp, np.int8, np.int16,
                             np.int32, np.int64, np.uint8, np.uint16,
                             np.uint32, np.uint64)):
            return int(data)
        elif isinstance(data, (np.float_, np.float16, np.float32, np.float64)):
            return float(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        return data 