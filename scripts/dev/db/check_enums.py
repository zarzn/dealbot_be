"""Script to check database enums."""

import asyncio
import asyncpg
from core.config import settings

async def check_enums():
    """Check the enum values in the database."""
    conn = await asyncpg.connect(
        user='postgres',
        password='12345678',
        database='agentic_deals',
        host='localhost'
    )
    
    try:
        # Check markettype enum
        result = await conn.fetch("""
            SELECT unnest(enum_range(NULL::markettype)) as value;
        """)
        market_types = [row['value'] for row in result]
        print("MarketType values:", market_types)

        # Check marketstatus enum
        result = await conn.fetch("""
            SELECT unnest(enum_range(NULL::marketstatus)) as value;
        """)
        market_statuses = [row['value'] for row in result]
        print("MarketStatus values:", market_statuses)

        # Check if values are lowercase
        for market_type in market_types:
            if market_type != market_type.lower():
                print(f"Warning: MarketType value '{market_type}' is not lowercase")

        for market_status in market_statuses:
            if market_status != market_status.lower():
                print(f"Warning: MarketStatus value '{market_status}' is not lowercase")

    except Exception as e:
        print(f"Error checking enums: {str(e)}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_enums()) 