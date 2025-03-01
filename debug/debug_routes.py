"""Debug script to print out all available routes in the FastAPI application."""

from fastapi import FastAPI
import uvicorn
import os
import sys

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the app from the main module
from core.main import app

def print_routes():
    """Print all available routes in the FastAPI application."""
    print("\n===== REGISTERED ROUTES =====")
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        name = getattr(route, "name", None)
        print(f"Path: {path}, Methods: {methods}, Name: {name}")
    print("============================\n")

if __name__ == "__main__":
    print_routes() 