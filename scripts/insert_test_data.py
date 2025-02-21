import asyncio
import asyncpg
import uuid
import json

async def insert_test_data():
    # Connect to the database
    conn = await asyncpg.connect(
        user='postgres',
        password='12345678',
        database='deals_test',  # Use test database
        host='localhost',
        port=5432
    )
    
    try:
        # Insert test market
        test_market_id = str(uuid.uuid4())
        config = json.dumps({'api_version': 'v1', 'region': 'US'})
        await conn.execute("""
            INSERT INTO markets (
                id, name, type, status, config
            ) VALUES (
                $1, $2, $3::markettype, $4::market_status, $5::jsonb
            )
        """, test_market_id, 'Amazon', 'amazon', 'active', config)
        
        print("Test market data inserted successfully")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(insert_test_data()) 