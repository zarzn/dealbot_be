"""Price prediction service using machine learning."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID

# Third-party imports
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.seasonal import seasonal_decompose
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from redis.asyncio import Redis

# Local application imports
from core.models.price_prediction import (
    PricePrediction,
    PricePredictionCreate,
    PricePredictionResponse,
    PricePredictionPoint,
    ModelPerformance,
    PriceAnalysis,
    PriceTrend
)
from core.models.price_tracking import PricePoint
from core.exceptions.price import (
    PricePredictionError,
    InsufficientDataError,
    ModelError
)
from core.utils.redis import get_redis_client
from core.utils.logger import get_logger
from core.services.base import BaseService
from core.repositories.price_prediction import PricePredictionRepository

logger = get_logger(__name__)

class PricePredictionService(BaseService):
    """Service for predicting price movements using ML."""

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Optional[Redis] = None,
        min_history_points: int = 30,
        confidence_threshold: float = 0.8
    ):
        self.repository = PricePredictionRepository(session)
        super().__init__(self.repository, session)
        self._redis_client = redis_client
        self.min_history_points = min_history_points
        self.confidence_threshold = confidence_threshold
        self.prophet_model = None
        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42
        )

    async def _get_redis(self) -> Redis:
        """Get Redis client instance."""
        if self._redis_client is None:
            self._redis_client = await get_redis_client()
        return self._redis_client

    async def create_prediction(
        self,
        prediction_data: PricePredictionCreate,
        user_id: UUID
    ) -> PricePredictionResponse:
        """Create a new price prediction."""
        try:
            # Get price history
            price_history = await self._get_price_history(prediction_data.deal_id)
            
            if len(price_history) < self.min_history_points:
                raise InsufficientDataError(
                    f"Need at least {self.min_history_points} price points"
                )
                
            # Generate predictions
            predictions = await self._generate_predictions(
                price_history,
                prediction_data.prediction_days,
                prediction_data.confidence_threshold
            )
            
            # Create prediction record
            prediction = PricePrediction(
                deal_id=prediction_data.deal_id,
                user_id=user_id,
                model_name='prophet',
                prediction_days=prediction_data.prediction_days,
                confidence_threshold=prediction_data.confidence_threshold,
                predictions=predictions['predictions'],
                overall_confidence=predictions['confidence'],
                trend_direction=predictions['trend']['direction'],
                trend_strength=predictions['trend']['strength'],
                seasonality_score=predictions.get('seasonality', {}).get('strength'),
                features_used=predictions.get('features_used'),
                model_params=prediction_data.model_params,
                meta_data=prediction_data.meta_data
            )
            
            self.session.add(prediction)
            await self.session.commit()
            await self.session.refresh(prediction)
            
            return PricePredictionResponse.model_validate(prediction)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating price prediction: {str(e)}")
            raise PricePredictionError(f"Failed to create prediction: {str(e)}")

    async def get_prediction(
        self,
        prediction_id: int,
        user_id: UUID
    ) -> Optional[PricePredictionResponse]:
        """Get a price prediction by ID."""
        try:
            prediction = await self._get_prediction(prediction_id, user_id)
            if not prediction:
                return None
                
            return PricePredictionResponse.model_validate(prediction)
            
        except Exception as e:
            logger.error(f"Error getting price prediction: {str(e)}")
            raise PricePredictionError(f"Failed to get prediction: {str(e)}")

    async def list_predictions(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[PricePredictionResponse]:
        """List all price predictions for a user."""
        try:
            query = (
                select(PricePrediction)
                .where(PricePrediction.user_id == user_id)
                .order_by(PricePrediction.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            
            result = await self.session.execute(query)
            predictions = result.scalars().all()
            
            return [PricePredictionResponse.model_validate(p) for p in predictions]
            
        except Exception as e:
            logger.error(f"Error listing price predictions: {str(e)}")
            raise PricePredictionError(f"Failed to list predictions: {str(e)}")

    async def get_deal_predictions(
        self,
        deal_id: UUID,
        user_id: UUID,
        days_ahead: int = 30
    ) -> List[PricePredictionResponse]:
        """Get price predictions for a deal."""
        try:
            # Get price history
            price_history = await self._get_price_history(deal_id)
            
            if len(price_history) < self.min_history_points:
                raise InsufficientDataError(
                    f"Need at least {self.min_history_points} price points"
                )
                
            # Generate new predictions
            predictions = await self._generate_predictions(
                price_history,
                days_ahead,
                self.confidence_threshold
            )
            
            # Create prediction record
            prediction = PricePrediction(
                deal_id=deal_id,
                user_id=user_id,
                model_name='prophet',
                prediction_days=days_ahead,
                confidence_threshold=self.confidence_threshold,
                predictions=predictions['predictions'],
                overall_confidence=predictions['confidence'],
                trend_direction=predictions['trend']['direction'],
                trend_strength=predictions['trend']['strength'],
                seasonality_score=predictions.get('seasonality', {}).get('strength'),
                features_used=predictions.get('features_used')
            )
            
            self.session.add(prediction)
            await self.session.commit()
            
            # Get recent predictions
            query = (
                select(PricePrediction)
                .where(
                    and_(
                        PricePrediction.deal_id == deal_id,
                        PricePrediction.user_id == user_id
                    )
                )
                .order_by(PricePrediction.created_at.desc())
                .limit(5)
            )
            
            result = await self.session.execute(query)
            predictions = result.scalars().all()
            
            return [PricePredictionResponse.model_validate(p) for p in predictions]
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error getting deal predictions: {str(e)}")
            raise PricePredictionError(f"Failed to get deal predictions: {str(e)}")

    async def analyze_deal_price(
        self,
        deal_id: UUID,
        user_id: UUID
    ) -> PriceAnalysis:
        """Get detailed price analysis for a deal."""
        try:
            # Get price history
            price_history = await self._get_price_history(deal_id)
            
            if len(price_history) < self.min_history_points:
                raise InsufficientDataError(
                    f"Need at least {self.min_history_points} price points"
                )
                
            # Prepare data
            df = pd.DataFrame(price_history)
            prices = df['price'].values
            timestamps = pd.to_datetime(df['timestamp'])
            
            # Analyze trend
            trend = await self._analyze_trend(prices, timestamps)
            
            # Analyze seasonality
            seasonality = await self._analyze_seasonality(prices, timestamps)
            
            # Detect anomalies
            anomalies = await self._detect_anomalies(prices)
            
            # Calculate additional metrics
            volatility = self._calculate_volatility(prices)
            forecast_quality = await self._evaluate_forecast_quality(deal_id)
            
            return PriceAnalysis(
                trend=trend,
                seasonality=seasonality,
                anomalies=anomalies,
                forecast_quality=forecast_quality,
                price_drivers=await self._analyze_price_drivers(deal_id),
                market_correlation=await self._calculate_market_correlation(deal_id),
                volatility_index=volatility,
                confidence_metrics={
                    'trend_confidence': trend.get('confidence', 0.0),
                    'seasonality_confidence': seasonality.get('confidence', 0.0),
                    'anomaly_confidence': 1.0 - (len(anomalies) / len(prices))
                },
                metadata={
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    'price_points_analyzed': len(prices),
                    'time_range': f"{(timestamps.max() - timestamps.min()).days} days"
                }
            )
            
        except Exception as e:
            logger.error(f"Error analyzing deal price: {str(e)}")
            raise PricePredictionError(f"Failed to analyze deal price: {str(e)}")

    async def get_price_trends(
        self,
        deal_id: UUID,
        user_id: UUID,
        timeframe: str = "1m"
    ) -> Dict[str, PriceTrend]:
        """Get price trends for different timeframes."""
        try:
            # Get price history
            price_history = await self._get_price_history(deal_id)
            
            if len(price_history) < self.min_history_points:
                raise InsufficientDataError(
                    f"Need at least {self.min_history_points} price points"
                )
                
            # Prepare data
            df = pd.DataFrame(price_history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Calculate trends for different timeframes
            trends = {}
            timeframes = {
                "1d": timedelta(days=1),
                "1w": timedelta(days=7),
                "1m": timedelta(days=30),
                "3m": timedelta(days=90)
            }
            
            for period, delta in timeframes.items():
                period_data = df[df['timestamp'] >= datetime.utcnow() - delta]
                if len(period_data) > 1:
                    trends[period] = await self._calculate_trend(period_data)
                    
            return trends
            
        except Exception as e:
            logger.error(f"Error getting price trends: {str(e)}")
            raise PricePredictionError(f"Failed to get price trends: {str(e)}")

    async def get_model_performance(
        self,
        user_id: UUID
    ) -> Dict[str, ModelPerformance]:
        """Get performance metrics for prediction models."""
        try:
            # Get recent predictions
            query = (
                select(PricePrediction)
                .where(PricePrediction.user_id == user_id)
                .order_by(PricePrediction.created_at.desc())
                .limit(100)
            )
            
            result = await self.session.execute(query)
            predictions = result.scalars().all()
            
            if not predictions:
                raise ModelError("No predictions found for performance analysis")
                
            # Calculate performance metrics by model
            performance_metrics = {}
            for prediction in predictions:
                if prediction.model_name not in performance_metrics:
                    performance_metrics[prediction.model_name] = []
                performance_metrics[prediction.model_name].append(prediction)
                
            # Calculate metrics for each model
            model_performance = {}
            for model_name, model_predictions in performance_metrics.items():
                metrics = await self._calculate_model_metrics(model_predictions)
                model_performance[model_name] = ModelPerformance(
                    model_name=model_name,
                    **metrics
                )
                
            return model_performance
            
        except Exception as e:
            logger.error(f"Error getting model performance: {str(e)}")
            raise PricePredictionError(f"Failed to get model performance: {str(e)}")

    async def _get_prediction(
        self,
        prediction_id: int,
        user_id: UUID
    ) -> Optional[PricePrediction]:
        """Get a prediction by ID and user ID."""
        query = (
            select(PricePrediction)
            .where(
                and_(
                    PricePrediction.id == prediction_id,
                    PricePrediction.user_id == user_id
                )
            )
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_price_history(
        self,
        deal_id: UUID,
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """Get price history for a deal."""
        try:
            # Try to get from cache first
            redis = await self._get_redis()
            cache_key = f"price_history:{deal_id}:{days}"
            cached_data = await redis.get(cache_key)
            
            if cached_data:
                return cached_data
            
            # Get from database
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = (
                select(PricePoint)
                .where(
                    and_(
                        PricePoint.deal_id == deal_id,
                        PricePoint.timestamp >= cutoff_date
                    )
                )
                .order_by(PricePoint.timestamp.asc())
            )
            
            result = await self.session.execute(query)
            price_points = result.scalars().all()
            
            if not price_points:
                return []
            
            # Format data
            history = [
                {
                    "price": point.price,
                    "timestamp": point.timestamp.isoformat(),
                    "source": point.source,
                    "meta_data": point.meta_data
                }
                for point in price_points
            ]
            
            # Cache the results
            await redis.setex(
                cache_key,
                timedelta(minutes=15),  # Cache for 15 minutes
                history
            )
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise PricePredictionError(f"Failed to get price history: {str(e)}")

    async def _generate_predictions(
        self,
        price_history: List[Dict[str, Any]],
        days_ahead: int,
        confidence_threshold: float
    ) -> Dict[str, Any]:
        """Generate price predictions using Prophet."""
        try:
            # Prepare data for Prophet
            df = pd.DataFrame(price_history)
            df['ds'] = pd.to_datetime(df['timestamp'])
            df['y'] = df['price']
            
            # Initialize and fit Prophet model
            self.prophet_model = Prophet(
                daily_seasonality=True,
                weekly_seasonality=True,
                yearly_seasonality=True,
                interval_width=0.95
            )
            self.prophet_model.fit(df)
            
            # Make future dataframe
            future = self.prophet_model.make_future_dataframe(
                periods=days_ahead,
                freq='D'
            )
            
            # Make predictions
            forecast = self.prophet_model.predict(future)
            
            # Extract predictions
            predictions = []
            for i in range(-days_ahead, 0):
                predictions.append({
                    'date': forecast['ds'].iloc[i].isoformat(),
                    'price': float(forecast['yhat'].iloc[i]),
                    'lower_bound': float(forecast['yhat_lower'].iloc[i]),
                    'upper_bound': float(forecast['yhat_upper'].iloc[i]),
                    'confidence': float(
                        1 - (
                            forecast['yhat_upper'].iloc[i] -
                            forecast['yhat_lower'].iloc[i]
                        ) / forecast['yhat'].iloc[i]
                    )
                })
                
            # Calculate overall metrics
            confidence = np.mean([p['confidence'] for p in predictions])
            trend = self._analyze_forecast_trend(forecast)
            
            return {
                'predictions': predictions,
                'confidence': float(confidence),
                'trend': trend,
                'features_used': ['historical_prices', 'seasonality', 'holidays']
            }
            
        except Exception as e:
            logger.error(f"Error generating predictions: {str(e)}")
            raise PricePredictionError(f"Failed to generate predictions: {str(e)}")

    def _analyze_forecast_trend(
        self,
        forecast: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze trend from forecast."""
        try:
            # Get trend component
            trend = forecast['trend'].values
            
            # Calculate trend direction and strength
            trend_diff = np.diff(trend)
            direction = 'up' if np.mean(trend_diff) > 0 else 'down'
            strength = float(np.abs(np.mean(trend_diff)) / np.std(trend))
            
            return {
                'direction': direction,
                'strength': min(1.0, strength)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing forecast trend: {str(e)}")
            return {'direction': 'unknown', 'strength': 0.0}

    async def _analyze_trend(
        self,
        prices: np.ndarray,
        timestamps: pd.Series
    ) -> Dict[str, float]:
        """Analyze price trend."""
        try:
            # Calculate trend using linear regression
            x = np.arange(len(prices)).reshape(-1, 1)
            y = prices.reshape(-1, 1)
            
            # Fit trend line
            slope = np.polyfit(x.flatten(), y.flatten(), 1)[0]
            
            # Calculate trend strength
            trend_strength = abs(slope) / np.mean(prices)
            
            return {
                'slope': float(slope),
                'strength': float(min(1.0, trend_strength)),
                'confidence': float(
                    1 - np.std(prices) / np.mean(prices)
                )
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trend: {str(e)}")
            return {'slope': 0.0, 'strength': 0.0, 'confidence': 0.0}

    async def _analyze_seasonality(
        self,
        prices: np.ndarray,
        timestamps: pd.Series
    ) -> Dict[str, float]:
        """Analyze price seasonality."""
        try:
            # Create time series
            ts = pd.Series(prices, index=timestamps)
            
            # Perform seasonal decomposition
            decomposition = seasonal_decompose(
                ts,
                period=7,  # Weekly seasonality
                extrapolate_trend='freq'
            )
            
            # Calculate seasonality strength
            seasonal_strength = float(
                np.std(decomposition.seasonal) /
                np.std(decomposition.resid)
            )
            
            return {
                'strength': min(1.0, seasonal_strength),
                'period': 7,
                'confidence': float(
                    1 - np.std(decomposition.resid) /
                    np.std(prices)
                )
            }
            
        except Exception as e:
            logger.error(f"Error analyzing seasonality: {str(e)}")
            return {
                'strength': 0.0,
                'period': 0,
                'confidence': 0.0
            }

    async def _detect_anomalies(
        self,
        prices: np.ndarray
    ) -> List[Dict[str, float]]:
        """Detect price anomalies."""
        try:
            # Fit anomaly detector
            self.anomaly_detector.fit(prices.reshape(-1, 1))
            
            # Get anomaly scores
            scores = self.anomaly_detector.score_samples(
                prices.reshape(-1, 1)
            )
            
            # Identify anomalies
            anomalies = []
            for i, score in enumerate(scores):
                if score < np.percentile(scores, 10):  # Bottom 10%
                    anomalies.append({
                        'index': i,
                        'price': float(prices[i]),
                        'score': float(score)
                    })
                    
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}")
            return []

    def _calculate_volatility(self, prices: np.ndarray) -> float:
        """Calculate price volatility."""
        try:
            if len(prices) < 2:
                return 0.0
                
            returns = np.diff(prices) / prices[:-1]
            return float(np.std(returns))
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            return 0.0

    async def _evaluate_forecast_quality(
        self,
        deal_id: UUID
    ) -> float:
        """Evaluate the quality of previous forecasts."""
        try:
            # Get recent predictions
            query = (
                select(PricePrediction)
                .where(PricePrediction.deal_id == deal_id)
                .order_by(PricePrediction.created_at.desc())
                .limit(10)
            )
            
            result = await self.session.execute(query)
            predictions = result.scalars().all()
            
            if not predictions:
                return 0.0
                
            # Calculate average confidence
            confidences = [p.overall_confidence for p in predictions]
            return float(np.mean(confidences))
            
        except Exception as e:
            logger.error(f"Error evaluating forecast quality: {str(e)}")
            return 0.0

    async def _analyze_price_drivers(
        self,
        deal_id: UUID
    ) -> List[Dict[str, float]]:
        """Analyze factors driving price changes."""
        try:
            # Get price history with metadata
            price_history = await self._get_price_history(deal_id)
            
            if not price_history:
                return []
                
            # Analyze metadata factors
            factors = {}
            for point in price_history:
                meta = point.get('meta_data', {})
                for factor, value in meta.items():
                    if isinstance(value, (int, float)):
                        if factor not in factors:
                            factors[factor] = []
                        factors[factor].append(value)
                        
            # Calculate correlation with price
            prices = [p['price'] for p in price_history]
            correlations = []
            
            for factor, values in factors.items():
                if len(values) == len(prices):
                    correlation = float(
                        np.corrcoef(prices, values)[0, 1]
                    )
                    correlations.append({
                        'factor': factor,
                        'correlation': correlation
                    })
                    
            return sorted(
                correlations,
                key=lambda x: abs(x['correlation']),
                reverse=True
            )
            
        except Exception as e:
            logger.error(f"Error analyzing price drivers: {str(e)}")
            return []

    async def _calculate_market_correlation(
        self,
        deal_id: UUID
    ) -> float:
        """Calculate correlation with market prices."""
        try:
            # Get deal price history
            deal_prices = await self._get_price_history(deal_id)
            
            if not deal_prices:
                return 0.0
                
            # Get market average prices (placeholder)
            market_prices = [p['price'] for p in deal_prices]  # Replace with actual market prices
            
            # Calculate correlation
            correlation = float(
                np.corrcoef(
                    [p['price'] for p in deal_prices],
                    market_prices
                )[0, 1]
            )
            
            return correlation
            
        except Exception as e:
            logger.error(f"Error calculating market correlation: {str(e)}")
            return 0.0

    async def _calculate_model_metrics(
        self,
        predictions: List[PricePrediction]
    ) -> Dict[str, Any]:
        """Calculate model performance metrics."""
        try:
            maes = []
            mapes = []
            rmses = []
            
            for pred in predictions:
                actual = [p['price'] for p in pred.predictions if p.get('actual')]
                predicted = [p['price'] for p in pred.predictions if p.get('predicted')]
                
                if actual and predicted:
                    mapes.append(
                        np.mean(np.abs(
                            (np.array(actual) - np.array(predicted)) / np.array(actual)
                        ))
                    )
                    maes.append(
                        np.mean(np.abs(np.array(actual) - np.array(predicted)))
                    )
                    rmses.append(
                        np.sqrt(np.mean((np.array(actual) - np.array(predicted)) ** 2))
                    )
            
            return {
                'mae': float(np.mean(maes)) if maes else None,
                'mape': float(np.mean(mapes)) if mapes else None,
                'rmse': float(np.mean(rmses)) if rmses else None,
                'sample_size': len(predictions)
            }
        except Exception as e:
            logger.error(f"Error calculating model metrics: {str(e)}")
            raise ModelError(f"Failed to calculate model metrics: {str(e)}") 