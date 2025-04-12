"""Unit tests for the SES email backend."""

import pytest
from unittest.mock import patch, MagicMock
import boto3

from core.services.email.backends.ses import SESEmailBackend
from core.config import settings


@pytest.fixture
def mock_boto3_client():
    """Create a mock boto3 SES client."""
    with patch('boto3.client') as mock_client:
        mock_ses = MagicMock()
        mock_ses.send_raw_email.return_value = {'MessageId': 'test-message-id'}
        mock_client.return_value = mock_ses
        yield mock_ses


@pytest.fixture
def mock_jinja_env():
    """Create a mock Jinja2 environment."""
    with patch('jinja2.Environment') as mock_env:
        mock_template = MagicMock()
        mock_template.render.return_value = "<html><body><h1>Test Email</h1></body></html>"
        mock_env_instance = MagicMock()
        mock_env_instance.get_template.return_value = mock_template
        mock_env.return_value = mock_env_instance
        yield mock_env


@pytest.mark.asyncio
async def test_ses_backend_initialization():
    """Test that the SES backend initializes correctly."""
    with patch('boto3.client') as mock_client:
        backend = SESEmailBackend()
        assert backend.region_name == settings.AWS_SES_REGION
        assert mock_client.called


@pytest.mark.asyncio
async def test_ses_send_email(mock_boto3_client, mock_jinja_env):
    """Test the send_email method."""
    # Create the backend
    backend = SESEmailBackend()
    
    # Test sending an email
    result = await backend.send_email(
        to_email="test@example.com",
        subject="Test Subject",
        template_name="test_template.html",
        template_data={"name": "Test User"},
        from_email="from@example.com"
    )
    
    # Verify the result
    assert result is True
    assert mock_boto3_client.send_raw_email.called
    
    # Check that the call arguments are correct
    call_kwargs = mock_boto3_client.send_raw_email.call_args[1]
    assert 'Source' in call_kwargs
    assert 'RawMessage' in call_kwargs
    assert 'Destinations' in call_kwargs
    assert 'test@example.com' in call_kwargs['Destinations']


@pytest.mark.asyncio
async def test_ses_send_email_with_multiple_recipients(mock_boto3_client, mock_jinja_env):
    """Test sending email to multiple recipients."""
    backend = SESEmailBackend()
    
    # Test sending an email to multiple recipients
    result = await backend.send_email(
        to_email=["test1@example.com", "test2@example.com"],
        subject="Test Subject",
        template_name="test_template.html",
        template_data={"name": "Test User"},
        from_email="from@example.com",
        cc=["cc@example.com"],
        bcc=["bcc@example.com"]
    )
    
    # Verify the result
    assert result is True
    assert mock_boto3_client.send_raw_email.called
    
    # Check that the recipients are correct
    call_kwargs = mock_boto3_client.send_raw_email.call_args[1]
    assert 'test1@example.com' in call_kwargs['Destinations']
    assert 'test2@example.com' in call_kwargs['Destinations']
    assert 'cc@example.com' in call_kwargs['Destinations']
    assert 'bcc@example.com' in call_kwargs['Destinations']


@pytest.mark.asyncio
async def test_ses_send_email_with_error(mock_boto3_client, mock_jinja_env):
    """Test error handling when sending email."""
    # Configure the mock to raise an exception
    mock_boto3_client.send_raw_email.side_effect = Exception("Test exception")
    
    # Create the backend with fail_silently=True
    backend = SESEmailBackend(fail_silently=True)
    
    # Test sending an email that will fail
    result = await backend.send_email(
        to_email="test@example.com",
        subject="Test Subject",
        template_name="test_template.html",
        template_data={"name": "Test User"}
    )
    
    # Verify the result
    assert result is False


@pytest.mark.asyncio
async def test_ses_send_email_raises_exception():
    """Test that exceptions are raised when fail_silently is False."""
    with patch('boto3.client') as mock_client:
        mock_ses = MagicMock()
        mock_ses.send_raw_email.side_effect = Exception("Test exception")
        mock_client.return_value = mock_ses
        
        # Create the backend with fail_silently=False
        backend = SESEmailBackend(fail_silently=False)
        
        # Test sending an email that will fail
        with pytest.raises(Exception):
            with patch('jinja2.Environment') as mock_env:
                mock_template = MagicMock()
                mock_template.render.return_value = "<html>Test</html>"
                mock_env_instance = MagicMock()
                mock_env_instance.get_template.return_value = mock_template
                mock_env.return_value = mock_env_instance
                
                await backend.send_email(
                    to_email="test@example.com",
                    subject="Test Subject",
                    template_name="test_template.html",
                    template_data={"name": "Test User"}
                ) 