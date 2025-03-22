"""A simplified share API router for testing.

This module provides a minimal implementation of share API endpoints
for debugging purposes.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/simple-share", tags=["simple-sharing"])
logger = logging.getLogger(__name__)


@router.get("")
async def test_get():
    """Simple test endpoint for GET requests."""
    return JSONResponse(content={"message": "GET test successful"})


@router.post("/test")
async def test_post():
    """Simple test endpoint for POST requests."""
    return JSONResponse(
        status_code=201,
        content={"message": "POST test successful"}
    ) 