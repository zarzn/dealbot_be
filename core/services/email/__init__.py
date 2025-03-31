"""Email service package."""

from core.services.email.email import (
    EmailService,
    send_reset_email,
    send_verification_email,
    send_magic_link_email,
    send_contact_form_email
)

email_service = EmailService()

async def get_email_service() -> EmailService:
    """Get the email service instance.
    
    Returns:
        EmailService: The email service instance.
    """
    return email_service

__all__ = [
    'EmailService',
    'send_reset_email',
    'send_verification_email',
    'send_magic_link_email',
    'send_contact_form_email',
    'email_service',
    'get_email_service',
] 