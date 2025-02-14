"""Price tracking and prediction related exceptions."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from .base_exceptions import BaseError

class PriceTrackingError(BaseError):
    """Base exception for price tracking errors."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.deal_id = deal_id
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'deal_id': self.deal_id,
            **self.details
        }

class PricePredictionError(BaseError):
    """Base exception for price prediction errors."""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.model_name = model_name
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'model_name': self.model_name,
            **self.details
        }

class InsufficientDataError(PricePredictionError):
    """Exception raised when there is not enough data for prediction."""
    
    def __init__(
        self,
        message: str,
        required_points: int,
        available_points: int,
        model_name: Optional[str] = None
    ):
        super().__init__(message, model_name)
        self.required_points = required_points
        self.available_points = available_points
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details.update({
            'required_points': self.required_points,
            'available_points': self.available_points
        })
        return details

class ModelError(PricePredictionError):
    """Exception raised when ML model operations fail."""
    
    def __init__(
        self,
        message: str,
        model_name: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, model_name)
        self.operation = operation
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details.update({
            'operation': self.operation,
            **self.details
        })
        return details

class DealScoreError(BaseError):
    """Exception raised when deal scoring fails."""
    
    def __init__(
        self,
        message: str,
        component: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.component = component
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'component': self.component,
            **self.details
        }

class PriceValidationError(PriceTrackingError):
    """Exception raised when price data validation fails."""
    
    def __init__(
        self,
        message: str,
        invalid_fields: Dict[str, str],
        deal_id: Optional[str] = None
    ):
        super().__init__(message, deal_id)
        self.invalid_fields = invalid_fields
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['invalid_fields'] = self.invalid_fields
        return details

class TrackerNotFoundError(PriceTrackingError):
    """Exception raised when a price tracker is not found."""
    pass

class PredictionNotFoundError(PricePredictionError):
    """Exception raised when a price prediction is not found."""
    pass

class InvalidTimeframeError(PricePredictionError):
    """Exception raised when an invalid timeframe is provided."""
    
    def __init__(
        self,
        message: str,
        valid_timeframes: List[str],
        model_name: Optional[str] = None
    ):
        super().__init__(message, model_name)
        self.valid_timeframes = valid_timeframes
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['valid_timeframes'] = self.valid_timeframes
        return details

class ModelTrainingError(ModelError):
    """Exception raised when model training fails."""
    
    def __init__(
        self,
        message: str,
        model_name: str,
        training_metrics: Optional[Dict[str, float]] = None
    ):
        super().__init__(message, model_name, operation="training")
        self.training_metrics = training_metrics or {}
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['training_metrics'] = self.training_metrics
        return details

class PredictionTimeoutError(PricePredictionError):
    """Exception raised when prediction takes too long."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: int,
        model_name: Optional[str] = None
    ):
        super().__init__(message, model_name)
        self.timeout_seconds = timeout_seconds
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['timeout_seconds'] = self.timeout_seconds
        return details

class DataSyncError(PriceTrackingError):
    """Exception raised when there are issues syncing price data."""
    
    def __init__(
        self,
        message: str,
        source: str,
        sync_details: Optional[Dict[str, Any]] = None,
        deal_id: Optional[str] = None
    ):
        super().__init__(message, deal_id)
        self.source = source
        self.sync_details = sync_details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details.update({
            'source': self.source,
            'sync_details': self.sync_details
        })
        return details

class ThresholdValidationError(PriceTrackingError):
    """Exception raised when price threshold validation fails."""
    
    def __init__(
        self,
        message: str,
        current_price: Decimal,
        threshold_price: Decimal,
        deal_id: Optional[str] = None
    ):
        super().__init__(message, deal_id)
        self.current_price = current_price
        self.threshold_price = threshold_price
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details.update({
            'current_price': str(self.current_price),
            'threshold_price': str(self.threshold_price)
        })
        return details

class AnalysisError(PricePredictionError):
    """Exception raised when price analysis fails."""
    
    def __init__(
        self,
        message: str,
        analysis_type: str,
        details: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None
    ):
        super().__init__(message, model_name)
        self.analysis_type = analysis_type
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details.update({
            'analysis_type': self.analysis_type,
            **self.details
        })
        return details 