"""Email service module."""

import logging
from typing import Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
import datetime

from core.config import settings
from core.services.email.backends.console import ConsoleEmailBackend
from core.services.email.backends.ses import SESEmailBackend

logger = logging.getLogger(__name__)

# Initialize Jinja2 environment for email templates
try:
    env = Environment(
        loader=FileSystemLoader(settings.EMAIL_TEMPLATES_DIR),
        autoescape=select_autoescape(['html', 'xml'])
    )
except Exception as e:
    logger.error(f"Failed to initialize Jinja2 environment: {e}")
    env = None

class EmailService:
    """Service for sending emails"""

    def __init__(self):
        # Determine which backend to use based on settings
        if settings.EMAIL_BACKEND == "ses":
            self.backend = SESEmailBackend()
            logger.info("Initialized EmailService with AWS SES backend")
        elif settings.EMAIL_BACKEND == "core.services.email.backends.console.ConsoleEmailBackend":
            self.backend = ConsoleEmailBackend()
            logger.info("Initialized EmailService with Console backend")
        else:
            self.backend = None
            logger.info("Initialized EmailService with default SMTP backend")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        template_data: Dict[str, Any],
        from_email: Optional[str] = None
    ) -> bool:
        """Send an email using configured SMTP settings and Jinja2 templates"""
        try:
            if env is None:
                raise ValueError("Email templates not initialized")

            # If using a backend
            if self.backend is not None:
                return await self.backend.send_email(
                    to_email=to_email,
                    subject=subject,
                    template_name=template_name,
                    template_data=template_data,
                    from_email=from_email or settings.EMAIL_FROM
                )

            # For SMTP backend, render the template
            template = env.get_template(template_name)
            html_content = template.render(**template_data)

            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = from_email or settings.EMAIL_FROM
            message['To'] = to_email

            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)

            # Send email
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                use_tls=settings.SMTP_USE_TLS
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

async def send_reset_email(email: str, token: str) -> bool:
    """Send password reset email."""
    email_service = EmailService()
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    
    return await email_service.send_email(
        to_email=email,
        subject="Password Reset Request",
        template_name="password_reset.html",
        template_data={
            "reset_link": reset_link,
            "expiry_hours": 24
        }
    )

async def send_verification_email(email: str, token: str) -> bool:
    """Send email verification email."""
    email_service = EmailService()
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    
    return await email_service.send_email(
        to_email=email,
        subject="Verify Your Email",
        template_name="email_verification.html",
        template_data={
            "verification_link": verification_link,
            "expiry_days": 7
        }
    )

async def send_magic_link_email(email: str, token: str) -> bool:
    """Send magic link email."""
    email_service = EmailService()
    login_link = f"{settings.FRONTEND_URL}/magic-link?token={token}"
    
    return await email_service.send_email(
        to_email=email,
        subject="Login Link",
        template_name="magic_link.html",
        template_data={
            "login_link": login_link,
            "expiry_minutes": 15
        }
    )

async def send_contact_form_email(name: str, email: str, message: str) -> bool:
    """Send contact form submission email to admin."""
    email_service = EmailService()
    
    # Use a safe approach to get email from settings with fallback
    admin_email = "admin@example.com"  # Default fallback
    
    if hasattr(settings, "ADMIN_EMAIL") and settings.ADMIN_EMAIL:
        admin_email = settings.ADMIN_EMAIL
    
    return await email_service.send_email(
        to_email=admin_email,
        subject=f"New Contact Form Submission from {name}",
        template_name="contact_form.html",
        template_data={
            "name": name,
            "email": email,
            "message": message,
            "year": datetime.datetime.now().year  # Add current year for template
        }
    )

email_service = EmailService() 