"""Console email backend for testing.

This module provides a console email backend that logs emails to the console
instead of actually sending them. This is useful for testing and development.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConsoleEmailBackend:
    """Email backend that writes emails to the console."""

    def __init__(self, fail_silently: bool = False, **kwargs: Any) -> None:
        """Initialize the console email backend.
        
        Args:
            fail_silently: Whether to raise exceptions on errors
            **kwargs: Additional configuration options
        """
        self.fail_silently = fail_silently

    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        template_data: Dict[str, Any],
        from_email: Optional[str] = None
    ) -> bool:
        """Send an email by logging it to the console.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            template_name: Name of the email template
            template_data: Data to render in the template
            from_email: Sender email address
            
        Returns:
            bool: True if the email was logged successfully
            
        Raises:
            Exception: If fail_silently is False and an error occurs
        """
        try:
            # Log the email details
            logger.info(
                "Sending test email:\n"
                f"From: {from_email}\n"
                f"To: {to_email}\n"
                f"Subject: {subject}\n"
                f"Template: {template_name}\n"
                f"Data: {template_data}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error sending test email: {str(e)}")
            if not self.fail_silently:
                raise
            return False 