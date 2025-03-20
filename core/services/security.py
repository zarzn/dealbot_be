"""Security service module.

This module provides functionality for security-related operations, including
suspicious activity detection and reporting.
"""

from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import logging
from datetime import datetime, timedelta
from ipaddress import ip_address, IPv4Address, IPv6Address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, and_
import json

from core.models.user import User
from core.models.auth_token import AuthToken
from core.services.base import BaseService
from core.exceptions import SecurityError, ValidationError
from core.notifications import TemplatedNotificationService
from core.models.enums import NotificationPriority

logger = logging.getLogger(__name__)

# Configure suspicious activity thresholds
THRESHOLDS = {
    "login_attempts": 5,  # Number of failed login attempts to trigger an alert
    "ip_change_distance": 1000,  # Distance in km that should trigger geolocation change alert
    "multiple_sessions": 10,  # Number of active sessions that triggers an alert
    "rapid_actions": 50,  # Number of actions in a short period that triggers an alert
    "rapid_actions_timeframe": 300,  # Timeframe in seconds for rapid actions
    "unusual_times_start": 23,  # Start hour for unusual activity time (11 PM)
    "unusual_times_end": 5,  # End hour for unusual activity time (5 AM)
}

class SecurityService(BaseService):
    """Service for security-related operations."""
    
    def __init__(self, session: AsyncSession):
        """Initialize security service.
        
        Args:
            session: Database session
        """
        super().__init__(session)
    
    async def detect_suspicious_activity(
        self,
        user_id: UUID,
        activity_type: str,
        activity_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Detect if an activity is suspicious.
        
        Args:
            user_id: User ID
            activity_type: Type of activity to check
            activity_data: Activity-specific data
            
        Returns:
            Tuple of (is_suspicious, reason)
        """
        try:
            # Check based on activity type
            if activity_type == "login":
                return await self._check_suspicious_login(user_id, activity_data)
            elif activity_type == "password_change":
                return await self._check_suspicious_password_change(user_id, activity_data)
            elif activity_type == "token_usage":
                return await self._check_suspicious_token_usage(user_id, activity_data)
            elif activity_type == "api_usage":
                return await self._check_suspicious_api_usage(user_id, activity_data)
            else:
                logger.warning(f"Unknown activity type for suspicious check: {activity_type}")
                return False, None
        except Exception as e:
            logger.error(f"Error detecting suspicious activity: {str(e)}")
            return False, None
    
    async def report_suspicious_activity(
        self,
        user_id: UUID,
        activity_type: str,
        reason: str,
        activity_data: Dict[str, Any],
        severity: str = "medium"
    ) -> UUID:
        """Report suspicious activity and send notification.
        
        Args:
            user_id: User ID
            activity_type: Type of suspicious activity
            reason: Reason why the activity is suspicious
            activity_data: Activity-specific data
            severity: Severity level (low, medium, high, critical)
            
        Returns:
            Notification ID
        """
        try:
            # Log the suspicious activity
            logger.warning(
                f"Suspicious activity detected: {activity_type}",
                extra={
                    "user_id": str(user_id),
                    "activity_type": activity_type,
                    "reason": reason,
                    "severity": severity
                }
            )
            
            # Create a notification
            notification_service = TemplatedNotificationService(self.session)
            
            # Set priority based on severity
            priority_map = {
                "low": NotificationPriority.LOW,
                "medium": NotificationPriority.MEDIUM,
                "high": NotificationPriority.HIGH,
                "critical": NotificationPriority.CRITICAL
            }
            priority = priority_map.get(severity, NotificationPriority.MEDIUM)
            
            # Format activity time
            activity_time = activity_data.get("timestamp", datetime.utcnow().isoformat())
            if isinstance(activity_time, datetime):
                activity_time = activity_time.strftime("%Y-%m-%d %H:%M:%S")
                
            # Get location info if available
            location = activity_data.get("location", "Unknown location")
            ip_address = activity_data.get("ip_address", "Unknown IP")
            
            # Create template parameters
            template_params = {
                "activity_type": activity_type.replace("_", " ").title(),
                "reason": reason,
                "location": location,
                "ip_address": ip_address,
                "activity_time": activity_time
            }
            
            # Send notification
            notification_id = await notification_service.send_notification(
                template_id="suspicious_activity",
                user_id=user_id,
                template_params=template_params,
                override_priority=priority,
                metadata={
                    "activity_type": activity_type,
                    "reason": reason,
                    "severity": severity,
                    "activity_data": activity_data
                },
                action_url="/security/activity"
            )
            
            return notification_id
            
        except Exception as e:
            logger.error(f"Error reporting suspicious activity: {str(e)}")
            raise SecurityError(f"Failed to report suspicious activity: {str(e)}")
    
    async def _check_suspicious_login(
        self,
        user_id: UUID,
        activity_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if a login attempt is suspicious.
        
        Args:
            user_id: User ID
            activity_data: Login-specific data
            
        Returns:
            Tuple of (is_suspicious, reason)
        """
        # Get user's recent login attempts
        stmt = select(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).order_by(desc(AuthToken.created_at))
        
        result = await self.session.execute(stmt)
        recent_tokens = result.scalars().all()
        
        # Check for multiple failed login attempts
        failed_attempts = [t for t in recent_tokens if not t.is_valid]
        if len(failed_attempts) >= THRESHOLDS["login_attempts"]:
            return True, f"Multiple failed login attempts ({len(failed_attempts)} in the last 24 hours)"
        
        # Check for login from new location
        if "geolocation" in activity_data and "ip_address" in activity_data:
            # Get user's common login locations
            common_locations = await self._get_common_locations(user_id)
            
            # Check if current location is significantly different
            current_location = activity_data["geolocation"]
            if current_location not in common_locations:
                return True, f"Login from unusual location: {current_location}"
        
        # Check for login at unusual times
        current_hour = datetime.utcnow().hour
        if current_hour >= THRESHOLDS["unusual_times_start"] or current_hour <= THRESHOLDS["unusual_times_end"]:
            # Check if user commonly logs in at this hour
            common_hours = await self._get_common_login_hours(user_id)
            if current_hour not in common_hours:
                return True, f"Login at unusual time: {current_hour}:00"
        
        return False, None
    
    async def _check_suspicious_password_change(
        self,
        user_id: UUID,
        activity_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if a password change is suspicious.
        
        Args:
            user_id: User ID
            activity_data: Password change data
            
        Returns:
            Tuple of (is_suspicious, reason)
        """
        # Check if password was changed from a new device/location
        if "device_id" in activity_data:
            common_devices = await self._get_common_devices(user_id)
            if activity_data["device_id"] not in common_devices:
                return True, "Password changed from new device"
        
        # Check if there were failed login attempts before password change
        time_window = datetime.utcnow() - timedelta(hours=24)
        
        stmt = select(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.created_at >= time_window,
            AuthToken.is_valid == False
        )
        
        result = await self.session.execute(stmt)
        failed_attempts = result.scalars().all()
        
        if len(failed_attempts) > 0:
            return True, f"Password change after {len(failed_attempts)} failed login attempts"
            
        return False, None
    
    async def _check_suspicious_token_usage(
        self,
        user_id: UUID,
        activity_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if token usage is suspicious.
        
        Args:
            user_id: User ID
            activity_data: Token usage data
            
        Returns:
            Tuple of (is_suspicious, reason)
        """
        # Check for unusual token usage patterns
        amount = activity_data.get("amount", 0)
        
        # Get user's average token usage
        average_usage = await self._get_average_token_usage(user_id)
        
        # If usage is significantly higher than average
        if average_usage > 0 and amount > average_usage * 3:
            return True, f"Unusually high token usage: {amount} (average: {average_usage})"
            
        return False, None
    
    async def _check_suspicious_api_usage(
        self,
        user_id: UUID,
        activity_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if API usage is suspicious.
        
        Args:
            user_id: User ID
            activity_data: API usage data
            
        Returns:
            Tuple of (is_suspicious, reason)
        """
        # Check for rapid API calls
        time_window = datetime.utcnow() - timedelta(seconds=THRESHOLDS["rapid_actions_timeframe"])
        
        # Count API calls in the time window
        from core.models.api_log import APILog
        stmt = select(func.count()).select_from(APILog).where(
            APILog.user_id == user_id,
            APILog.timestamp >= time_window
        )
        
        result = await self.session.execute(stmt)
        call_count = result.scalar_one() or 0
        
        if call_count > THRESHOLDS["rapid_actions"]:
            return True, f"Unusually high API usage rate: {call_count} calls in {THRESHOLDS['rapid_actions_timeframe']} seconds"
            
        return False, None
    
    async def _get_common_locations(self, user_id: UUID) -> List[str]:
        """Get user's common login locations.
        
        Args:
            user_id: User ID
            
        Returns:
            List of common locations
        """
        # This would get common locations from historical login data
        # For now, return an empty list which will make all locations appear new
        return []
    
    async def _get_common_login_hours(self, user_id: UUID) -> List[int]:
        """Get user's common login hours.
        
        Args:
            user_id: User ID
            
        Returns:
            List of hour values (0-23)
        """
        # This would analyze historical login patterns
        # For now, return a typical work day
        return list(range(8, 20))  # 8 AM to 8 PM
    
    async def _get_common_devices(self, user_id: UUID) -> List[str]:
        """Get user's common devices.
        
        Args:
            user_id: User ID
            
        Returns:
            List of device IDs
        """
        # This would get common devices from historical login data
        # For now, return an empty list which will make all devices appear new
        return []
    
    async def _get_average_token_usage(self, user_id: UUID) -> float:
        """Get user's average token usage per transaction.
        
        Args:
            user_id: User ID
            
        Returns:
            Average token usage
        """
        # This would analyze historical token transactions
        # For now, return a default value
        return 10.0 