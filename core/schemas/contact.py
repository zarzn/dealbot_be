"""Contact form schemas."""

from pydantic import BaseModel, EmailStr, Field


class ContactFormRequest(BaseModel):
    """Contact form request schema."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(...)
    message: str = Field(..., min_length=10, max_length=2000)


class ContactFormResponse(BaseModel):
    """Contact form response schema."""
    success: bool
    message: str 