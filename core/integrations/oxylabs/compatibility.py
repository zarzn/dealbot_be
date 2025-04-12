"""Compatibility layer for Oxylabs integration.

This module provides backward compatibility with the original oxylabs.py implementation
while using the new modular architecture underneath.
"""

import asyncio
import base64
import json
import logging
import os
import re
import time
import hashlib
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

import aiohttp
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import MarketIntegrationError
from core.models.enums import MarketType
from core.config import settings
from core.integrations.oxylabs.client import get_oxylabs_client, OxylabsClient

logger = logging.getLogger(__name__)

# Country code to location mappings
COUNTRY_TO_LOCATION = {
    "us": "United States",
    "ca": "Canada",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "it": "Italy",
    "es": "Spain",
    "jp": "Japan",
    "cn": "China",
    "br": "Brazil",
    "mx": "Mexico",
    "in": "India",
    "ru": "Russia"
}

class OxylabsService:
    """Compatibility service for interacting with Oxylabs.
    
    This class provides the same interface as the original OxylabsService
    but uses the new modular architecture under the hood.
    """
    
    def __init__(
        self,
        username: Optional[Union[str, SecretStr]] = None,
        password: Optional[Union[str, SecretStr]] = None,
        base_url: Optional[str] = None,
        redis_client: Optional[Any] = None,
        db: Optional[AsyncSession] = None
    ):
        # Extract actual string values from SecretStr if needed
        if isinstance(username, SecretStr):
            self.username = username.get_secret_value()
        else:
            self.username = str(username) if username is not None else settings.OXYLABS_USERNAME
            
        if isinstance(password, SecretStr):
            self.password = password.get_secret_value()
        else:
            if password is not None:
                self.password = str(password)
            elif hasattr(settings.OXYLABS_PASSWORD, 'get_secret_value'):
                self.password = settings.OXYLABS_PASSWORD.get_secret_value()
            else:
                self.password = str(settings.OXYLABS_PASSWORD)

        # Log credential status to help with debugging
        logger.info(f"Oxylabs credentials configured in compatibility layer: username={bool(self.username)}, password={bool(self.password)}")
        
        self.base_url = base_url or "https://realtime.oxylabs.io"
        self.redis_client = redis_client
        self.db = db
        
        # Create the client
        self._client = OxylabsClient(
            username=self.username, 
            password=self.password,
            db=self.db
        )
        
        # These properties are kept for compatibility but not actively used
        self.concurrent_limit = getattr(settings, "OXYLABS_CONCURRENT_LIMIT", 15)
        self.semaphore = asyncio.Semaphore(self.concurrent_limit)
        self.timeouts = {
            MarketType.AMAZON.value.lower(): aiohttp.ClientTimeout(total=20),
            MarketType.GOOGLE_SHOPPING.value.lower(): aiohttp.ClientTimeout(total=60),
            MarketType.WALMART.value.lower(): aiohttp.ClientTimeout(total=25),
            "default": aiohttp.ClientTimeout(total=20)
        }
        self.requests_per_second = getattr(settings, "OXYLABS_REQUESTS_PER_SECOND", 5)
        self.monthly_limit = getattr(settings, "OXYLABS_MONTHLY_LIMIT", 100000)

    # Compatibility methods that map to the new architecture
    async def search_amazon(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on Amazon using the new modular architecture."""
        # Handle cache_ttl for Redis caching if not explicitly provided
        if self.redis_client and "cache_ttl" not in kwargs:
            # Default cache time of 1 hour for search queries
            kwargs["cache_ttl"] = 3600  # 1 hour
        return await self._client.search_amazon(query, **kwargs)

    async def get_amazon_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on Amazon using the new modular architecture."""
        # Handle cache_ttl for Redis caching if not explicitly provided
        if self.redis_client and "cache_ttl" not in kwargs:
            # Default cache time of 24 hours for product details
            kwargs["cache_ttl"] = 86400  # 24 hours
        return await self._client.get_amazon_product(product_id, **kwargs)

    async def search_walmart(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on Walmart using the new modular architecture."""
        # Handle cache_ttl for Redis caching if not explicitly provided
        if self.redis_client and "cache_ttl" not in kwargs:
            # Default cache time of 1 hour for search queries
            kwargs["cache_ttl"] = 3600  # 1 hour
        return await self._client.search_walmart(query, **kwargs)

    async def get_walmart_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on Walmart using the new modular architecture."""
        # Handle cache_ttl for Redis caching if not explicitly provided
        if self.redis_client and "cache_ttl" not in kwargs:
            # Default cache time of 24 hours for product details
            kwargs["cache_ttl"] = 86400  # 24 hours
        return await self._client.get_walmart_product(product_id, **kwargs)

    async def search_google_shopping(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on Google Shopping using the new modular architecture."""
        # Handle cache_ttl for Redis caching if not explicitly provided
        if self.redis_client and "cache_ttl" not in kwargs:
            # Default cache time of 1 hour for search queries
            kwargs["cache_ttl"] = 3600  # 1 hour
        return await self._client.search_google_shopping(query, **kwargs)

    async def get_google_shopping_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on Google Shopping using the new modular architecture."""
        # Handle cache_ttl for Redis caching if not explicitly provided
        if self.redis_client and "cache_ttl" not in kwargs:
            # Default cache time of 24 hours for product details
            kwargs["cache_ttl"] = 86400  # 24 hours
        return await self._client.get_google_shopping_product(product_id, **kwargs)

    async def search_ebay(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search for products on eBay using the new modular architecture."""
        # Handle cache_ttl for Redis caching if not explicitly provided
        if self.redis_client and "cache_ttl" not in kwargs:
            # Default cache time of 1 hour for search queries
            kwargs["cache_ttl"] = 3600  # 1 hour
        return await self._client.search_ebay(query, **kwargs)

    async def get_ebay_product(self, product_id: str, **kwargs) -> Dict[str, Any]:
        """Get details of a specific product on eBay using the new modular architecture."""
        # Handle cache_ttl for Redis caching if not explicitly provided
        if self.redis_client and "cache_ttl" not in kwargs:
            # Default cache time of 24 hours for product details
            kwargs["cache_ttl"] = 86400  # 24 hours
        return await self._client.get_ebay_product(product_id, **kwargs)

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self._client.close()


# Global service instance for singleton pattern
_oxylabs_service = None

async def get_oxylabs(
    username: Optional[Union[str, SecretStr]] = None,
    password: Optional[Union[str, SecretStr]] = None,
    db: Optional[AsyncSession] = None,
    redis_client: Optional[Any] = None,
    register_cleanup: bool = True
) -> OxylabsService:
    """Factory function to create or retrieve an OxylabsService instance.
    
    This function ensures a single instance of OxylabsService is used across the application.
    
    Args:
        username: Optional username for Oxylabs API
        password: Optional password for Oxylabs API
        db: Optional database session for metrics recording
        redis_client: Optional Redis client for caching
        register_cleanup: Whether to register cleanup method with FastAPI shutdown event
        
    Returns:
        An instance of OxylabsService
    """
    global _oxylabs_service
    
    # Return existing instance if available
    if _oxylabs_service is not None:
        return _oxylabs_service
    
    # Create a new service instance
    service = OxylabsService(
        username=username,
        password=password,
        db=db,
        redis_client=redis_client
    )
    
    # Store service instance in global variable
    _oxylabs_service = service
    
    # Register cleanup with FastAPI if available
    if register_cleanup:
        try:
            # Try to find the FastAPI app
            app = None
            
            # Try to get it from the main module
            try:
                import sys
                if 'main' in sys.modules:
                    main_module = sys.modules['main']
                    if hasattr(main_module, 'app'):
                        app = main_module.app
            except Exception as e:
                logger.debug(f"Could not get FastAPI app from main module: {str(e)}")
            
            # If we found an app, register the shutdown handler
            if app is not None and hasattr(app, 'on_event'):
                @app.on_event("shutdown")
                async def shutdown_oxylabs_service():
                    logger.info("Shutting down Oxylabs service")
                    try:
                        await service.cleanup()
                    except Exception as e:
                        logger.error(f"Error during Oxylabs service shutdown: {str(e)}")
                
                logger.info("Successfully registered Oxylabs service cleanup with FastAPI shutdown event")
            else:
                logger.warning("Could not find FastAPI app for shutdown event registration")
                
        except Exception as e:
            logger.warning(f"Error registering cleanup with FastAPI: {str(e)}")
    
    return service 