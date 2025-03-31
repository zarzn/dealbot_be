"""Contact form API router."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from core.schemas import ContactFormRequest, ContactFormResponse
from core.services.email import send_contact_form_email

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/",
    response_model=ContactFormResponse,
    summary="Submit contact form",
    description="Submits a contact form and sends an email to the site administrators",
)
async def submit_contact_form(
    data: ContactFormRequest,
) -> ContactFormResponse:
    """
    Submit a contact form.
    
    This endpoint accepts contact form submissions and sends an email to the site admin.
    
    Args:
        data: The contact form data including name, email, and message.
        
    Returns:
        A response indicating success or failure.
        
    Raises:
        HTTPException: If there was an error sending the email.
    """
    try:
        # Log the contact form submission
        logger.info(f"Contact form submission from {data.email}")
        
        success = await send_contact_form_email(
            name=data.name,
            email=data.email,
            message=data.message
        )
        
        if not success:
            logger.error(f"Failed to send contact form email from {data.email}")
            raise HTTPException(
                status_code=500,
                detail="Failed to send contact form email. Please try again later."
            )
            
        return ContactFormResponse(
            success=True,
            message="Your message has been sent. We'll get back to you soon!"
        )
    
    except Exception as e:
        logger.exception(f"Error processing contact form: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An error occurred while processing your contact form. Please try again later."
        ) 