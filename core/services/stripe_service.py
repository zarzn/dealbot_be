"""Stripe payment service."""

import stripe
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone

from fastapi import HTTPException, status
from core.config import settings
from core.exceptions import PaymentError, PaymentValidationError, ValidationError

logger = logging.getLogger(__name__)

class StripeService:
    """Stripe payment service for handling payments."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize stripe service."""
        self.api_key = api_key or settings.STRIPE_SECRET_KEY
        if not self.api_key:
            logger.error("Stripe API key is not set")
            raise PaymentError("Stripe API key is not configured")
        
        # Initialize Stripe
        stripe.api_key = self.api_key
        self.stripe = stripe
    
    async def create_payment_intent(
        self, 
        amount: float, 
        currency: str = "usd",
        payment_method_types: List[str] = ["card"],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a payment intent for token purchase.
        
        Args:
            amount: Amount in dollars
            currency: Currency code
            payment_method_types: List of payment method types
            metadata: Additional metadata
            
        Returns:
            Payment intent details
        """
        try:
            logger.info(f"Creating payment intent: {amount} {currency}")
            
            # Convert to cents for Stripe (Stripe expects amounts in smallest currency unit)
            amount_in_cents = int(amount * 100)
            
            if amount_in_cents <= 0:
                raise ValidationError("Amount must be positive")
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency=currency,
                payment_method_types=payment_method_types,
                metadata=metadata or {}
            )
            
            logger.info(f"Created payment intent: {payment_intent.id}")
            
            return {
                "client_secret": payment_intent.client_secret,
                "payment_intent_id": payment_intent.id,
                "amount": amount,
                "currency": currency,
                "status": payment_intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise PaymentError(f"Stripe payment error: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            raise PaymentError(f"Payment processing error: {str(e)}")
    
    async def verify_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Verify payment intent status.
        
        Args:
            payment_intent_id: Payment intent ID
            
        Returns:
            Payment verification details
        """
        try:
            logger.info(f"Verifying payment intent: {payment_intent_id}")
            
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if not payment_intent:
                raise PaymentError("Payment not found")
            
            is_success = payment_intent.status == "succeeded"
            
            return {
                "payment_intent_id": payment_intent.id,
                "amount": payment_intent.amount / 100,  # Convert back to dollars
                "currency": payment_intent.currency,
                "status": payment_intent.status,
                "success": is_success,
                "metadata": payment_intent.metadata,
                "payment_method": payment_intent.payment_method,
                "created": datetime.fromtimestamp(payment_intent.created, tz=timezone.utc)
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error verifying payment: {str(e)}")
            raise PaymentError(f"Stripe payment verification error: {str(e)}")
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            raise PaymentError(f"Payment verification error: {str(e)}")
    
    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook events.
        
        Args:
            payload: Webhook payload
            signature: Webhook signature
            
        Returns:
            Processed event details
        """
        try:
            logger.info("Processing Stripe webhook")
            
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET
            )
            
            logger.info(f"Webhook event type: {event.type}")
            
            # Handle different webhook events
            if event.type == "payment_intent.succeeded":
                payment_intent = event.data.object
                logger.info(f"Payment succeeded: {payment_intent.id}")
                # Process the successful payment
                return {
                    "success": True,
                    "event_type": event.type,
                    "payment_intent_id": payment_intent.id,
                    "amount": payment_intent.amount / 100,
                    "metadata": payment_intent.metadata
                }
                
            elif event.type == "payment_intent.payment_failed":
                payment_intent = event.data.object
                logger.warning(f"Payment failed: {payment_intent.id}")
                return {
                    "success": False,
                    "event_type": event.type,
                    "payment_intent_id": payment_intent.id,
                    "error": payment_intent.last_payment_error
                }
                
            # Return basic info for other event types
            return {
                "success": True,
                "event_type": event.type,
                "event_id": event.id
            }
            
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid webhook signature")
            raise PaymentError("Invalid webhook signature")
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            raise PaymentError(f"Webhook processing error: {str(e)}")

async def get_stripe_service() -> StripeService:
    """Get Stripe service instance."""
    return StripeService() 