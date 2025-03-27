"""Email client utilities for interacting with the email service.

This module provides a simple client interface for sending emails through the core.services.email
service. It's a wrapper around the email service to make it easier to use in various parts of the
application.
"""

import logging
from typing import Dict, Any, Optional, List, Union
from uuid import UUID

from core.services.email import email_service, EmailService

logger = logging.getLogger(__name__)

class EmailClient:
    """Client for sending emails.
    
    This is a wrapper around the EmailService to provide a simpler interface
    for sending emails from various parts of the application.
    """
    
    def __init__(self, service: Optional[EmailService] = None):
        """Initialize the email client.
        
        Args:
            service: Optional email service instance. If not provided,
                the global email_service instance will be used.
        """
        self.service = service or email_service
    
    async def send_email(
        self,
        to_email: Union[str, List[str]],
        subject: str,
        template_name: str,
        template_data: Dict[str, Any],
        from_email: Optional[str] = None
    ) -> bool:
        """Send an email using the email service.
        
        Args:
            to_email: Recipient email address or list of addresses
            subject: Email subject
            template_name: Name of the email template to use
            template_data: Data to render in the template
            from_email: Optional sender email address
            
        Returns:
            bool: True if the email was sent successfully, False otherwise
        """
        try:
            # Handle list of recipients
            if isinstance(to_email, list):
                success = True
                for recipient in to_email:
                    result = await self.service.send_email(
                        to_email=recipient,
                        subject=subject,
                        template_name=template_name,
                        template_data=template_data,
                        from_email=from_email
                    )
                    success = success and result
                return success
            
            # Single recipient
            return await self.service.send_email(
                to_email=to_email,
                subject=subject,
                template_name=template_name,
                template_data=template_data,
                from_email=from_email
            )
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    async def send_verification_email(self, email: str, token: str) -> bool:
        """Send email verification.
        
        Args:
            email: Recipient email address
            token: Verification token
            
        Returns:
            bool: True if the email was sent successfully
        """
        from core.services.email import send_verification_email
        return await send_verification_email(email, token)
    
    async def send_reset_email(self, email: str, token: str) -> bool:
        """Send password reset email.
        
        Args:
            email: Recipient email address
            token: Reset token
            
        Returns:
            bool: True if the email was sent successfully
        """
        from core.services.email import send_reset_email
        return await send_reset_email(email, token)
    
    async def send_magic_link_email(self, email: str, token: str) -> bool:
        """Send magic link email.
        
        Args:
            email: Recipient email address
            token: Magic link token
            
        Returns:
            bool: True if the email was sent successfully
        """
        from core.services.email import send_magic_link_email
        return await send_magic_link_email(email, token) 