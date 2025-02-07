#!/usr/bin/env python
"""Script to initialize the database tables."""

import asyncio
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database.init_db import init_database

async def main():
    """Initialize the database."""
    try:
        await init_database()
        print("Database initialization completed successfully")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 