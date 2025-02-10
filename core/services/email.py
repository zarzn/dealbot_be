"""Email service module."""

import logging
from typing import Dict, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.config import settings

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

    @staticmethod
    async def send_email(
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

            template = env.get_template(template_name)
            html_content = template.render(**template_data)

            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = from_email or settings.EMAIL_FROM
            message["To"] = to_email

            # Add HTML content
            message.attach(MIMEText(html_content, "html"))

            # Send email
            await aiosmtplib.send(
                message,
                hostname=settings.EMAIL_SERVER_HOST,
                port=settings.EMAIL_SERVER_PORT,
                username=settings.EMAIL_SERVER_USER,
                password=settings.EMAIL_SERVER_PASSWORD,
                use_tls=settings.EMAIL_USE_TLS
            )

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

email_service = EmailService() 