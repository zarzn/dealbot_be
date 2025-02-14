"""Price prediction module using machine learning techniques."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.seasonal import seasonal_decompose
from core.utils.logger import get_logger
from core.exceptions import PricePredictionError
from core.database.redis import RedisClient

logger = get_logger(__name__)

class PricePredictor:
    """Price prediction service using machine learning."""
    
    def __init__(
        self,
        redis_client: RedisClient,
        min_history_points: int = 30,
        confidence_threshold: float = 0.8,
        seasonality_threshold: float = 0.3
    ):
        self.redis_client = redis_client
        self.min_history_points = min_history_points
        self.confidence_threshold = confidence_threshold
        self.seasonality_threshold = seasonality_threshold
        
    async def predict_price_movement(
        self,
        deal_id: str,
        forecast_days: int = 7
    ) -> Dict[str, Any]:
        """Predict future price movements using Prophet."""
        try:
            # Get price history
            price_history = await self._get_price_history(deal_id)
            
            if len(price_history) < self.min_history_points:
                raise PricePredictionError(
                    "Insufficient price history for prediction"
                )
                
            # Prepare data for Prophet
            df = pd.DataFrame(price_history)
            df['ds'] = pd.to_datetime(df['timestamp'])
            df['y'] = df['price']
            
            # Initialize and fit Prophet model
            model = Prophet(
                daily_seasonality=True,
                weekly_seasonality=True,
                yearly_seasonality=True,
                interval_width=0.95
            )
            model.fit(df)
            
            # Create future dataframe
            future = model.make_future_dataframe(
                periods=forecast_days,
                freq='D'
            )
            
            # Make predictions
            forecast = model.predict(future)
            
            # Calculate prediction confidence
            confidence = await self._calculate_prediction_confidence(
                forecast,
                df['y'].values
            )
            
            # Analyze trend
            trend_direction, trend_strength = await self._analyze_trend(
                forecast
            )
            
            # Extract seasonality
            seasonality = await self._extract_seasonality(df['y'].values)
            
            return {
                'forecast': {
                    'dates': forecast['ds'].tail(forecast_days).dt.strftime('%Y-%m-%d').tolist(),
                    'prices': forecast['yhat'].tail(forecast_days).round(2).tolist(),
                    'lower_bound': forecast['yhat_lower'].tail(forecast_days).round(2).tolist(),
                    'upper_bound': forecast['yhat_upper'].tail(forecast_days).round(2).tolist()
                },
                'confidence': confidence,
                'trend': {
                    'direction': trend_direction,
                    'strength': trend_strength
                },
                'seasonality': seasonality,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error predicting price movement: {str(e)}")
            raise PricePredictionError(f"Prediction failed: {str(e)}")
            
    async def detect_anomalies(
        self,
        deal_id: str,
        contamination: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Detect price anomalies using Isolation Forest."""
        try:
            # Get price history
            price_history = await self._get_price_history(deal_id)
            
            if len(price_history) < self.min_history_points:
                raise PricePredictionError(
                    "Insufficient price history for anomaly detection"
                )
                
            # Prepare data
            prices = np.array([p['price'] for p in price_history]).reshape(-1, 1)
            
            # Initialize and fit Isolation Forest
            iso_forest = IsolationForest(
                contamination=contamination,
                random_state=42
            )
            predictions = iso_forest.fit_predict(prices)
            
            # Identify anomalies
            anomalies = []
            for i, pred in enumerate(predictions):
                if pred == -1:  # Anomaly
                    anomalies.append({
                        'timestamp': price_history[i]['timestamp'],
                        'price': price_history[i]['price'],
                        'score': float(iso_forest.score_samples(
                            prices[i].reshape(1, -1)
                        )[0])
                    })
                    
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}")
            raise PricePredictionError(f"Anomaly detection failed: {str(e)}")
            
    async def analyze_seasonality(
        self,
        deal_id: str,
        period: Optional[int] = None
    ) -> Dict[str, Any]:
        """Analyze price seasonality using seasonal decomposition."""
        try:
            # Get price history
            price_history = await self._get_price_history(deal_id)
            
            if len(price_history) < self.min_history_points:
                raise PricePredictionError(
                    "Insufficient price history for seasonality analysis"
                )
                
            # Prepare data
            prices = pd.Series(
                [p['price'] for p in price_history],
                index=pd.to_datetime([p['timestamp'] for p in price_history])
            )
            
            # If period not provided, try to detect it
            if not period:
                period = self._detect_seasonality_period(prices)
                
            # Perform seasonal decomposition
            decomposition = seasonal_decompose(
                prices,
                period=period,
                extrapolate_trend='freq'
            )
            
            # Calculate seasonality strength
            seasonality_strength = await self._calculate_seasonality_strength(
                decomposition
            )
            
            return {
                'has_seasonality': seasonality_strength >= self.seasonality_threshold,
                'seasonality_strength': seasonality_strength,
                'period': period,
                'components': {
                    'trend': decomposition.trend.tolist(),
                    'seasonal': decomposition.seasonal.tolist(),
                    'residual': decomposition.resid.tolist()
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing seasonality: {str(e)}")
            raise PricePredictionError(f"Seasonality analysis failed: {str(e)}")
            
    async def _get_price_history(
        self,
        deal_id: str
    ) -> List[Dict[str, Any]]:
        """Get price history from Redis."""
        try:
            history = await self.redis_client.lrange(
                f"price_history:{deal_id}",
                0,
                -1
            )
            
            if not history:
                raise PricePredictionError("No price history found")
                
            return sorted(
                history,
                key=lambda x: x['timestamp']
            )
            
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise PricePredictionError(f"Failed to get price history: {str(e)}")
            
    async def _calculate_prediction_confidence(
        self,
        forecast: pd.DataFrame,
        actual_prices: np.ndarray
    ) -> float:
        """Calculate prediction confidence score."""
        try:
            # Use the width of prediction intervals
            interval_width = np.mean(
                forecast['yhat_upper'] - forecast['yhat_lower']
            )
            price_range = np.max(actual_prices) - np.min(actual_prices)
            
            # Calculate confidence score (0 to 1)
            confidence = 1 - (interval_width / (price_range * 2))
            return max(0, min(1, confidence))
            
        except Exception as e:
            logger.error(f"Error calculating prediction confidence: {str(e)}")
            return 0.0
            
    async def _analyze_trend(
        self,
        forecast: pd.DataFrame
    ) -> Tuple[str, float]:
        """Analyze price trend direction and strength."""
        try:
            # Get trend component
            trend = forecast['trend'].values
            
            # Calculate trend direction
            trend_diff = np.diff(trend)
            direction = 'up' if np.mean(trend_diff) > 0 else 'down'
            
            # Calculate trend strength (0 to 1)
            strength = np.abs(np.mean(trend_diff)) / np.std(trend)
            strength = max(0, min(1, strength))
            
            return direction, strength
            
        except Exception as e:
            logger.error(f"Error analyzing trend: {str(e)}")
            return 'unknown', 0.0
            
    async def _extract_seasonality(
        self,
        prices: np.ndarray
    ) -> Dict[str, Any]:
        """Extract seasonality patterns from price data."""
        try:
            # Calculate daily, weekly, and monthly patterns
            n_points = len(prices)
            
            patterns = {
                'daily': None,
                'weekly': None,
                'monthly': None
            }
            
            if n_points >= 24:  # At least 24 hours
                daily_pattern = np.mean(
                    prices[:-(n_points % 24)].reshape(-1, 24),
                    axis=0
                )
                patterns['daily'] = daily_pattern.tolist()
                
            if n_points >= 168:  # At least 1 week
                weekly_pattern = np.mean(
                    prices[:-(n_points % 168)].reshape(-1, 168),
                    axis=0
                )
                patterns['weekly'] = weekly_pattern.tolist()
                
            if n_points >= 720:  # At least 1 month
                monthly_pattern = np.mean(
                    prices[:-(n_points % 720)].reshape(-1, 720),
                    axis=0
                )
                patterns['monthly'] = monthly_pattern.tolist()
                
            return patterns
            
        except Exception as e:
            logger.error(f"Error extracting seasonality: {str(e)}")
            return {}
            
    def _detect_seasonality_period(
        self,
        prices: pd.Series
    ) -> int:
        """Detect the most likely seasonality period."""
        try:
            # Try common periods
            periods = [24, 168, 720]  # daily, weekly, monthly
            
            best_period = 24  # default to daily
            min_residual = float('inf')
            
            for period in periods:
                if len(prices) >= period * 2:
                    decomposition = seasonal_decompose(
                        prices,
                        period=period,
                        extrapolate_trend='freq'
                    )
                    residual = np.mean(np.abs(decomposition.resid))
                    
                    if residual < min_residual:
                        min_residual = residual
                        best_period = period
                        
            return best_period
            
        except Exception as e:
            logger.error(f"Error detecting seasonality period: {str(e)}")
            return 24  # default to daily
            
    async def _calculate_seasonality_strength(
        self,
        decomposition: Any
    ) -> float:
        """Calculate the strength of seasonality."""
        try:
            # Calculate variance of seasonal and residual components
            seasonal_var = np.var(decomposition.seasonal)
            residual_var = np.var(decomposition.resid)
            
            # Calculate strength (0 to 1)
            total_var = seasonal_var + residual_var
            strength = seasonal_var / total_var if total_var > 0 else 0
            
            return max(0, min(1, strength))
            
        except Exception as e:
            logger.error(f"Error calculating seasonality strength: {str(e)}")
            return 0.0 