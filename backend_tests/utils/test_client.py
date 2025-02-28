"""Test client utilities module."""

from fastapi.testclient import TestClient
from typing import Dict, Any, Optional, Union
import os
import asyncio
import httpx
from core.main import app

class APITestClient:
    """API test client wrapper that ensures the proper URL prefix is used."""
    
    def __init__(self, client: Optional[Union[TestClient, httpx.AsyncClient]] = None, base_url: str = "/api/v1"):
        """Initialize with a TestClient and base URL."""
        if client is None:
            # Create a default client if none provided
            self.client = TestClient(app)
        else:
            self.client = client
        self.base_url = base_url
        self.headers = {}
    
    def _build_url(self, url: str) -> str:
        """Build the proper URL with prefix if not already present."""
        # For URLs starting with http:// or https://, return as is
        if url.startswith(("http://", "https://")):
            return url
            
        # For URLs already starting with the base_url, return as is
        if url.startswith(self.base_url):
            return url
        
        # If url starts with /, remove it to avoid double slashes
        if url.startswith("/"):
            url = url[1:]
            
        return f"{self.base_url}/{url}"
    
    def get(self, url: str, **kwargs) -> Any:
        """Send a GET request with the proper URL prefix."""
        proper_url = self._build_url(url)
        print(f"APITestClient GET: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        return self.client.get(proper_url, **kwargs)
    
    def post(self, url: str, **kwargs) -> Any:
        """Send a POST request with the proper URL prefix."""
        proper_url = self._build_url(url)
        print(f"APITestClient POST: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        return self.client.post(proper_url, **kwargs)
    
    def put(self, url: str, **kwargs) -> Any:
        """Send a PUT request with the proper URL prefix."""
        proper_url = self._build_url(url)
        print(f"APITestClient PUT: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        return self.client.put(proper_url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> Any:
        """Send a DELETE request with the proper URL prefix."""
        proper_url = self._build_url(url)
        print(f"APITestClient DELETE: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        return self.client.delete(proper_url, **kwargs)
    
    def patch(self, url: str, **kwargs) -> Any:
        """Send a PATCH request with the proper URL prefix."""
        proper_url = self._build_url(url)
        print(f"APITestClient PATCH: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        return self.client.patch(proper_url, **kwargs)
    
    # Async methods for compatibility with async tests
    async def aget(self, url: str, **kwargs) -> Any:
        """Async wrapper for GET request."""
        proper_url = self._build_url(url)
        print(f"APITestClient async GET: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        if isinstance(self.client, TestClient):
            # Handle TestClient (sync)
            return self.client.get(proper_url, **kwargs)
        else:
            # Handle AsyncClient
            return await self.client.get(proper_url, **kwargs)
    
    async def apost(self, url: str, **kwargs) -> Any:
        """Async wrapper for POST request."""
        proper_url = self._build_url(url)
        print(f"APITestClient async POST: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        if isinstance(self.client, TestClient):
            # Handle TestClient (sync)
            return self.client.post(proper_url, **kwargs)
        else:
            # Handle AsyncClient
            return await self.client.post(proper_url, **kwargs)
    
    async def aput(self, url: str, **kwargs) -> Any:
        """Async wrapper for PUT request."""
        proper_url = self._build_url(url)
        print(f"APITestClient async PUT: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        if isinstance(self.client, TestClient):
            # Handle TestClient (sync)
            return self.client.put(proper_url, **kwargs)
        else:
            # Handle AsyncClient
            return await self.client.put(proper_url, **kwargs)
    
    async def adelete(self, url: str, **kwargs) -> Any:
        """Async wrapper for DELETE request."""
        proper_url = self._build_url(url)
        print(f"APITestClient async DELETE: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        if isinstance(self.client, TestClient):
            # Handle TestClient (sync)
            return self.client.delete(proper_url, **kwargs)
        else:
            # Handle AsyncClient
            return await self.client.delete(proper_url, **kwargs)
    
    async def apatch(self, url: str, **kwargs) -> Any:
        """Async wrapper for PATCH request."""
        proper_url = self._build_url(url)
        print(f"APITestClient async PATCH: {proper_url}")
        
        # Merge headers
        headers = {**self.headers, **(kwargs.get('headers', {}))}
        kwargs['headers'] = headers
        
        if isinstance(self.client, TestClient):
            # Handle TestClient (sync)
            return self.client.patch(proper_url, **kwargs)
        else:
            # Handle AsyncClient
            return await self.client.patch(proper_url, **kwargs)

def create_api_test_client(client: Union[TestClient, httpx.AsyncClient]) -> APITestClient:
    """Create an API test client wrapper."""
    return APITestClient(client) 