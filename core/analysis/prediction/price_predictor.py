"""Price prediction module using machine learning."""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import IsolationForest
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose
from prophet import Prophet

from core.exceptions import PredictionError
from core.utils.logger import get_logger
from core.utils.metrics import MetricsCollector

logger = get_logger(__name__)

class PricePredictor:
    """Advanced price prediction using multiple ML models."""
    
    def __init__(self):
        self.scaler = MinMaxScaler()
        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_jobs=-1
        )
        self.prophet_model = None
        
    async def predict_price_movement(
        self,
        price_history: List[Dict[str, Any]],
        prediction_days: int = 7
    ) -> Dict[str, Any]:
        """Predict future price movements."""
        try:
            if not price_history or len(price_history) < 30:
                raise PredictionError("Insufficient price history for prediction")
                
            # Prepare data
            df = pd.DataFrame(price_history)
            df['ds'] = pd.to_datetime(df['timestamp'])
            df['y'] = df['price']
            
            # Initialize and fit Prophet model
            self.prophet_model = Prophet(
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=10.0,
                seasonality_mode='multiplicative',
                daily_seasonality=True,
                weekly_seasonality=True,
                yearly_seasonality=True
            )
            self.prophet_model.fit(df)
            
            # Make future dataframe
            future = self.prophet_model.make_future_dataframe(
                periods=prediction_days,
                freq='D'
            )
            
            # Predict
            forecast = self.prophet_model.predict(future)
            
            # Extract predictions
            predictions = []
            for i in range(-prediction_days, 0):
                predictions.append({
                    'date': forecast['ds'].iloc[i].isoformat(),
                    'price': round(float(forecast['yhat'].iloc[i]), 2),
                    'price_lower': round(float(forecast['yhat_lower'].iloc[i]), 2),
                    'price_upper': round(float(forecast['yhat_upper'].iloc[i]), 2)
                })
                
            # Calculate confidence
            confidence = self._calculate_prediction_confidence(forecast, df)
            
            return {
                'predictions': predictions,
                'confidence': confidence,
                'trend': self._analyze_trend(forecast),
                'seasonality': self._extract_seasonality(df),
                'analysis_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error predicting price movement: {str(e)}")
            raise PredictionError(f"Failed to predict price movement: {str(e)}")
            
    async def detect_anomalies(
        self,
        price_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Detect anomalies in price history."""
        try:
            if not price_history:
                raise PredictionError("No price history provided")
                
            # Prepare data
            prices = np.array([p['price'] for p in price_history]).reshape(-1, 1)
            timestamps = [p['timestamp'] for p in price_history]
            
            # Fit anomaly detector
            anomaly_labels = self.anomaly_detector.fit_predict(prices)
            
            # Find anomalies
            anomalies = []
            for i, label in enumerate(anomaly_labels):
                if label == -1:  # Anomaly
                    anomalies.append({
                        'timestamp': timestamps[i],
                        'price': float(prices[i][0]),
                        'score': float(self.anomaly_detector.score_samples(prices[i].reshape(1, -1))[0])
                    })
                    
            return {
                'anomalies': anomalies,
                'anomaly_count': len(anomalies),
                'analysis_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}")
            raise PredictionError(f"Failed to detect anomalies: {str(e)}")
            
    async def analyze_seasonality(
        self,
        price_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze seasonal patterns in price history."""
        try:
            if not price_history or len(price_history) < 30:
                raise PredictionError("Insufficient data for seasonality analysis")
                
            # Prepare data
            df = pd.DataFrame(price_history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            df = df.asfreq('D')  # Ensure daily frequency
            
            # Perform seasonal decomposition
            decomposition = seasonal_decompose(
                df['price'],
                period=7,  # Weekly seasonality
                extrapolate_trend='freq'
            )
            
            return {
                'trend': decomposition.trend.tolist(),
                'seasonal': decomposition.seasonal.tolist(),
                'residual': decomposition.resid.tolist(),
                'strength': self._calculate_seasonality_strength(decomposition),
                'analysis_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing seasonality: {str(e)}")
            raise PredictionError(f"Failed to analyze seasonality: {str(e)}")
            
    def _calculate_prediction_confidence(
        self,
        forecast: pd.DataFrame,
        historical: pd.DataFrame
    ) -> float:
        """Calculate confidence in predictions."""
        try:
            # Calculate prediction interval width
            interval_width = (forecast['yhat_upper'] - forecast['yhat_lower']) / forecast['yhat']
            
            # Calculate historical accuracy
            historical_predictions = forecast[forecast['ds'].isin(historical['ds'])]
            historical_actual = historical.set_index('ds')['y']
            mape = np.mean(np.abs((historical_actual - historical_predictions['yhat']) / historical_actual))
            
            # Combine metrics
            confidence = (1 - mape) * (1 - np.mean(interval_width))
            
            return float(min(max(confidence, 0), 1))
            
        except Exception as e:
            logger.error(f"Error calculating prediction confidence: {str(e)}")
            return 0.5
            
    def _analyze_trend(self, forecast: pd.DataFrame) -> str:
        """Analyze the trend direction from forecast."""
        try:
            # Calculate trend from last 7 days of forecast
            last_week = forecast.tail(7)['yhat'].values
            trend_direction = np.polyfit(range(7), last_week, 1)[0]
            
            if trend_direction > 0:
                return 'increasing'
            elif trend_direction < 0:
                return 'decreasing'
            else:
                return 'stable'
                
        except Exception as e:
            logger.error(f"Error analyzing trend: {str(e)}")
            return 'unknown'
            
    def _extract_seasonality(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """Extract seasonal patterns from data."""
        try:
            # Daily pattern
            daily_pattern = df.groupby(df['ds'].dt.hour)['y'].mean().tolist()
            
            # Weekly pattern
            weekly_pattern = df.groupby(df['ds'].dt.dayofweek)['y'].mean().tolist()
            
            # Monthly pattern
            monthly_pattern = df.groupby(df['ds'].dt.day)['y'].mean().tolist()
            
            return {
                'daily': daily_pattern,
                'weekly': weekly_pattern,
                'monthly': monthly_pattern
            }
            
        except Exception as e:
            logger.error(f"Error extracting seasonality: {str(e)}")
            return {'daily': [], 'weekly': [], 'monthly': []}
            
    def _calculate_seasonality_strength(self, decomposition) -> float:
        """Calculate the strength of seasonality."""
        try:
            # Variance of seasonal component vs total variance
            seasonal_var = np.var(decomposition.seasonal)
            total_var = np.var(decomposition.seasonal + decomposition.resid)
            
            strength = seasonal_var / total_var if total_var > 0 else 0
            return float(min(max(strength, 0), 1))
            
        except Exception as e:
            logger.error(f"Error calculating seasonality strength: {str(e)}")
            return 0.0 