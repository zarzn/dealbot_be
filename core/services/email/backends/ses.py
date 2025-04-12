"""AWS SES email backend.

This module provides an email backend that sends emails using
AWS Simple Email Service (SES).
"""

import logging
import json
import boto3
from botocore.exceptions import ClientError
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List, Union

from core.config import settings

logger = logging.getLogger(__name__)

class SESEmailBackend:
    """Email backend that sends emails using AWS Simple Email Service (SES)."""

    def __init__(self, fail_silently: bool = False, **kwargs: Any) -> None:
        """Initialize the SES email backend.
        
        Args:
            fail_silently: Whether to raise exceptions on errors
            **kwargs: Additional configuration options
        """
        self.fail_silently = fail_silently
        self.region_name = kwargs.get('region_name', settings.AWS_SES_REGION)
        self.aws_access_key_id = kwargs.get('aws_access_key_id', settings.AWS_ACCESS_KEY_ID)
        self.aws_secret_access_key = kwargs.get('aws_secret_access_key', settings.AWS_SECRET_ACCESS_KEY)
        self.aws_session_token = kwargs.get('aws_session_token', getattr(settings, 'AWS_SESSION_TOKEN', None))
        self.configuration_set = kwargs.get('configuration_set', getattr(settings, 'SES_CONFIGURATION_SET', None))
        
        # Log configuration but hide sensitive values
        logger.info(
            f"Initializing SES backend with region {self.region_name}, "
            f"configuration_set: {self.configuration_set}"
        )
        
        # Initialize the SES client
        try:
            self.client = self._get_client()
            logger.info("AWS SES client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AWS SES client: {str(e)}")
            if not fail_silently:
                raise

    def _get_client(self):
        """Get a boto3 SES client with the specified configuration.
        
        Returns:
            boto3.client: SES client
        """
        # Create the client with the specified credentials
        # If credentials are not provided, boto3 will look for credentials in the
        # standard locations (environment variables, ~/.aws/credentials, etc.)
        client_kwargs = {'service_name': 'ses', 'region_name': self.region_name}
        
        # Only add credentials if they are provided and not empty strings
        if self.aws_access_key_id and self.aws_secret_access_key:
            logger.info("Using explicitly provided AWS credentials")
            client_kwargs.update({
                'aws_access_key_id': self.aws_access_key_id,
                'aws_secret_access_key': self.aws_secret_access_key
            })
            
            # Add session token if provided
            if self.aws_session_token:
                client_kwargs['aws_session_token'] = self.aws_session_token
        else:
            logger.info("Using AWS credentials from environment or AWS CLI configuration")
        
        return boto3.client(**client_kwargs)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        template_data: Dict[str, Any],
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send an email using AWS SES.
        
        Args:
            to_email: Recipient email address or list of addresses
            subject: Email subject
            template_name: Name of the email template
            template_data: Data to render in the template
            from_email: Sender email address
            cc: List of CC recipients
            bcc: List of BCC recipients
            reply_to: List of Reply-To addresses
            attachments: List of attachments as dicts with keys:
                        - filename: Name of the file
                        - content: Content of the file
                        - mimetype: MIME type of the file
            
        Returns:
            bool: True if the email was sent successfully
            
        Raises:
            Exception: If fail_silently is False and an error occurs
        """
        try:
            from core.config import settings
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            
            # Initialize Jinja2 environment for email templates
            try:
                env = Environment(
                    loader=FileSystemLoader(settings.EMAIL_TEMPLATES_DIR),
                    autoescape=select_autoescape(['html', 'xml'])
                )
            except Exception as e:
                logger.error(f"Failed to initialize Jinja2 environment: {e}")
                if not self.fail_silently:
                    raise
                return False
            
            # Render the template
            template = env.get_template(template_name)
            html_content = template.render(**template_data)
            
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = from_email or settings.EMAIL_FROM
            
            # Handle multiple recipients
            if isinstance(to_email, list):
                message['To'] = ', '.join(to_email)
            else:
                message['To'] = to_email
                to_email = [to_email]
            
            # Handle CC and BCC
            if cc:
                message['Cc'] = ', '.join(cc)
            if bcc:
                message['Bcc'] = ', '.join(bcc)
            
            # Handle Reply-To
            if reply_to:
                message['Reply-To'] = ', '.join(reply_to)
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    filename = attachment['filename']
                    content = attachment['content']
                    mimetype = attachment.get('mimetype', 'application/octet-stream')
                    
                    part = MIMEText(content, mimetype)
                    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    message.attach(part)
            
            # Convert the message to a raw string
            raw_message = message.as_string()
            
            # Send email using SES
            response = self.client.send_raw_email(
                Source=message['From'],
                Destinations=to_email + (cc or []) + (bcc or []),
                RawMessage={'Data': raw_message}
            )
            
            logger.info(f"Email sent successfully via SES: {response.get('MessageId')}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email via SES: {str(e)}")
            if not self.fail_silently:
                raise
            return False 