"""Email service module.

This module provides email sending functionality for the AI Agentic Deals System.
"""

import logging
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from jinja2 import Environment, PackageLoader, select_autoescape

from core.config import settings
from core.models.user import User

logger = logging.getLogger(__name__)

# Initialize Jinja2 environment for email templates
try:
    env = Environment(
        loader=PackageLoader('core', 'templates/email'),
        autoescape=select_autoescape(['html', 'xml'])
    )
except Exception as e:
    logger.warning(f"Failed to initialize Jinja2 environment: {e}")
    env = None

async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """Send an email using SMTP.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        text_content: Plain text content of the email
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_FROM_EMAIL
        msg['To'] = to_email

        # Add plain text version
        if text_content:
            msg.attach(MIMEText(text_content, 'plain'))

        # Add HTML version
        msg.attach(MIMEText(html_content, 'html'))

        # Connect to SMTP server and send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

async def send_verification_email(user: User, verification_token: str) -> bool:
    """Send email verification link to user.
    
    Args:
        user: User to send verification email to
        verification_token: Token for email verification
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        if env is None:
            raise ValueError("Email templates not initialized")

        template = env.get_template('verification.html')
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
        
        html_content = template.render(
            user_email=user.email,
            verification_url=verification_url
        )

        text_content = f"""
        Please verify your email address by clicking the link below:
        {verification_url}
        
        If you did not create an account, please ignore this email.
        """

        return await send_email(
            to_email=user.email,
            subject="Verify your email address",
            html_content=html_content,
            text_content=text_content
        )

    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        return False

async def send_password_reset_email(user: User, reset_token: str) -> bool:
    """Send password reset link to user.
    
    Args:
        user: User to send password reset email to
        reset_token: Token for password reset
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        if env is None:
            raise ValueError("Email templates not initialized")

        template = env.get_template('password_reset.html')
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        html_content = template.render(
            user_email=user.email,
            reset_url=reset_url
        )

        text_content = f"""
        You have requested to reset your password. Click the link below to proceed:
        {reset_url}
        
        If you did not request a password reset, please ignore this email.
        """

        return await send_email(
            to_email=user.email,
            subject="Reset your password",
            html_content=html_content,
            text_content=text_content
        )

    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        return False

async def send_deal_notification_email(user: User, deal_data: dict) -> bool:
    """Send deal notification email to user.
    
    Args:
        user: User to send notification to
        deal_data: Dictionary containing deal information
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        if env is None:
            raise ValueError("Email templates not initialized")

        template = env.get_template('deal_notification.html')
        deal_url = deal_data.get('url', '#')
        
        html_content = template.render(
            user_email=user.email,
            deal_title=deal_data.get('title', 'New Deal'),
            deal_price=deal_data.get('price', 'N/A'),
            deal_description=deal_data.get('description', ''),
            deal_url=deal_url
        )

        text_content = f"""
        A new deal matching your criteria has been found!
        
        {deal_data.get('title', 'New Deal')}
        Price: {deal_data.get('price', 'N/A')}
        
        View deal: {deal_url}
        """

        return await send_email(
            to_email=user.email,
            subject="New Deal Alert!",
            html_content=html_content,
            text_content=text_content
        )

    except Exception as e:
        logger.error(f"Failed to send deal notification email: {str(e)}")
        return False

__all__ = [
    'send_email',
    'send_verification_email',
    'send_password_reset_email',
    'send_deal_notification_email'
] 