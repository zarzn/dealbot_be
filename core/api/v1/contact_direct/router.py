"""Contact direct form API router."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from core.schemas import ContactFormRequest, ContactFormResponse
from core.services.email import send_contact_form_email

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/",
    response_model=ContactFormResponse
)
async def submit_contact_form(data: ContactFormRequest) -> ContactFormResponse:
    """
    Submit contact form and send email to site administrators.
    """
    try:
        logger.info(f"Contact form submission from {data.email}")
        
        # Send email
        email_sent = await send_contact_form_email(
            name=data.name,
            email=data.email,
            message=data.message
        )
        
        if not email_sent:
            logger.error(f"Failed to send contact form email from {data.email}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send contact form email. Please try again later."
            )
        
        return ContactFormResponse(success=True, message="Your message has been sent. We'll get back to you soon!")
    
    except Exception as e:
        logger.exception(f"Error processing contact form: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request."
        ) 