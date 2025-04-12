# Email Service Documentation

This document provides information about the email service implementation in the AI Agentic Deals System.

## Email Service Architecture

The email service follows a flexible backend pattern that allows for different email delivery methods:

- `ConsoleEmailBackend`: For development, logs emails to the console
- `SESEmailBackend`: For production, sends emails via AWS Simple Email Service (SES)

## AWS SES Configuration

To use AWS SES for sending emails, the following environment variables should be configured:

```
# Email Configuration
EMAIL_BACKEND="ses"
EMAIL_FROM="RebatOn <noreply@rebaton.ai>"

# AWS SES Configuration
AWS_SES_REGION="us-east-1"
AWS_ACCESS_KEY_ID="your_access_key_id"
AWS_SECRET_ACCESS_KEY="your_secret_access_key"
```

Optional AWS SES settings:
```
# Optional SES Configuration
AWS_SES_SOURCE_ARN="arn:aws:ses:region:account-id:identity/rebaton.ai"
AWS_SES_CONFIGURATION_SET="your-configuration-set-name"
```

## Email Verification Requirements

When using AWS SES:

1. **Sandbox Mode (default for new AWS accounts):**
   - Both sender and recipient email addresses must be verified
   - Use the AWS SES verification process to verify email addresses
   - Limited sending quota (typically 200 emails per 24 hours)

2. **Production Mode:**
   - Only sender email addresses/domains need verification
   - Request production access through AWS console
   - Higher sending quota

## Verifying Email Addresses

To verify an email address for use with AWS SES:

```powershell
aws ses verify-email-identity --email-address noreply@rebaton.ai --region us-east-1
```

After running this command, AWS will send a verification email to the provided address. The recipient must click the verification link in that email.

## Verifying Domains

To verify a domain for use with AWS SES:

```powershell
./scripts/aws/setup_ses_email.ps1 -Domain "rebaton.ai" -Region "us-east-1"
```

This script will:
1. Start the domain verification process
2. Provide the DNS records that need to be added to your domain
3. Configure DKIM for improved deliverability

## Testing Email Functionality

To test the AWS SES email functionality:

```powershell
python -m scripts.test_ses_email recipient@example.com
```

For unit testing without actual AWS calls:

```powershell
python scripts/test_ses_backend.py
```

## Using the Email Service

```python
from core.services.email.email import EmailService

async def send_example_email():
    email_service = EmailService()
    
    result = await email_service.send_email(
        to_email="recipient@example.com",
        subject="Example Email",
        template_name="notification.html",
        template_data={
            "title": "Example Notification",
            "content": "This is an example email notification."
        }
    )
    
    return result
```

The service also provides specialized email functions:
- `send_reset_email`: For password reset requests
- `send_verification_email`: For email verification
- `send_magic_link_email`: For passwordless login
- `send_contact_form_email`: For contact form submissions

## Email Templates

Email templates are located in `backend/core/templates/email/` and use Jinja2 templating. Available templates:

- `base_email.html`: Base template that others extend
- `password_reset.html`: Password reset email
- `email_verification.html`: Email verification
- `magic_link.html`: Magic link login
- `deal_notification.html`: Deal notifications
- `contact_form.html`: Contact form submissions
- `token_low_email.html`: Low token balance notifications
- `goal_completed_email.html`: Goal completion notifications
- `system_email.html`: System notifications

## Troubleshooting

Common issues and solutions:

1. **Email Not Sent**
   - Check AWS SES verification status
   - Ensure AWS credentials are correct
   - Confirm SES is out of sandbox mode or recipient is verified

2. **Permission Denied**
   - Ensure IAM user has appropriate SES permissions
   - Required permissions: `ses:SendEmail`, `ses:SendRawEmail`

3. **Email Bounces**
   - Check for proper DKIM setup
   - Verify sender domain has proper SPF records
   - Monitor bounce notifications from AWS 