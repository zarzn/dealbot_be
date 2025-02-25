"""Email service package."""

from core.services.email.email import (
    EmailService,
    send_reset_email,
    send_verification_email,
    send_magic_link_email
)

email_service = EmailService()

__all__ = [
    'EmailService',
    'send_reset_email',
    'send_verification_email',
    'send_magic_link_email',
    'email_service',
] 