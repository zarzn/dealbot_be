import asyncio
import asyncpg
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_db():
    """Check database tables and structure."""
    try:
        # Connect to the database
        conn = await asyncpg.connect(
            user='postgres',
            password='12345678',
            database='agentic_deals',
            host='localhost'
        )
        
        # Get PostgreSQL version
        version = await conn.fetchval('SELECT version();')
        print(f"\nPostgreSQL Version: {version}")
        
        # List all tables in public schema
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        if tables:
            print("\nTables in database:")
            for table in tables:
                print(f"- {table['table_name']}")
        else:
            print("\nNo tables found in database!")
        
        # Check enum types
        enums = await conn.fetch("""
            SELECT t.typname as enum_name,
                   e.enumlabel as enum_value
            FROM pg_type t
            JOIN pg_enum e on t.oid = e.enumtypid
            ORDER BY t.typname, e.enumsortorder;
        """)
        
        if enums:
            print("\nEnum types:")
            current_enum = None
            for enum in enums:
                if enum['enum_name'] != current_enum:
                    current_enum = enum['enum_name']
                    print(f"\n  {current_enum}:")
                print(f"    - {enum['enum_value']}")
        else:
            print("\nNo enum types found!")
        
        # Check alembic version
        version = await conn.fetchval('SELECT version_num FROM alembic_version;')
        print(f"\nCurrent alembic version: {version}")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Error checking database: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(check_db()) 