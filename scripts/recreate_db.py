import asyncio
import asyncpg

async def recreate_db():
    # Connect to default database to drop and create test database
    conn = await asyncpg.connect(
        user='postgres',
        password='12345678',
        database='postgres',  # Connect to default database
        host='localhost',
        port=5432
    )
    
    try:
        # Drop test database if it exists
        await conn.execute("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'deals_test'
            AND pid <> pg_backend_pid();
        """)
        await conn.execute('DROP DATABASE IF EXISTS deals_test')
        print("Dropped deals_test database")
        
        # Create test database
        await conn.execute('CREATE DATABASE deals_test')
        print("Created deals_test database")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(recreate_db()) 