import asyncio
import asyncpg

async def reset_db():
    conn = await asyncpg.connect(
        user='postgres',
        password='12345678',
        database='agentic_deals',
        host='localhost'
    )
    
    # Drop all tables in the database
    await conn.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
    """)
    
    # Drop all enum types
    await conn.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT typname FROM pg_type WHERE typtype = 'e') LOOP
                EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
            END LOOP;
        END $$;
    """)
    
    await conn.close()
    print("Database reset complete!")

async def check_version():
    conn = await asyncpg.connect(
        user='postgres',
        password='12345678',
        database='agentic_deals',
        host='localhost'
    )
    
    # Check if alembic_version table exists
    exists = await conn.fetch("""
        SELECT EXISTS (
            SELECT FROM pg_tables
            WHERE schemaname = 'public' 
            AND tablename = 'alembic_version'
        );
    """)
    
    if exists[0]['exists']:
        version = await conn.fetch('SELECT version_num FROM alembic_version;')
        print("\nCurrent alembic version:", version[0]['version_num'] if version else None)
    else:
        print("\nNo alembic_version table found")
    
    await conn.close()

async def check_db():
    conn = await asyncpg.connect(
        user='postgres',
        password='12345678',
        database='agentic_deals',
        host='localhost'
    )
    
    # Check database connection info
    version = await conn.fetchval('SELECT version();')
    print(f"\nPostgreSQL Version: {version}")
    
    # List all schemas
    schemas = await conn.fetch("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast');
    """)
    print("\nSchemas:")
    for schema in schemas:
        print(f"- {schema['schema_name']}")
    
    # List all tables in all schemas
    print("\nTables by schema:")
    for schema in schemas:
        schema_name = schema['schema_name']
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = $1 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """, schema_name)
        if tables:
            print(f"\n{schema_name} schema:")
            for table in tables:
                print(f"- {table['table_name']}")
    
    # Check enum types
    enums = await conn.fetch("""
        SELECT t.typname as enum_name,
               e.enumlabel as enum_value
        FROM pg_type t
        JOIN pg_enum e on t.oid = e.enumtypid
        ORDER BY t.typname, e.enumsortorder;
    """)
    
    if enums:
        print("\nEnum types and their values:")
        current_enum = None
        for enum in enums:
            if enum['enum_name'] != current_enum:
                current_enum = enum['enum_name']
                print(f"\n{current_enum}:")
            print(f"- {enum['enum_value']}")
    else:
        print("\nNo enum types found")

    # Check if tracked_deals table exists and its columns
    table_info = await conn.fetch("""
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE lower(table_name) = lower('tracked_deals')
        ORDER BY ordinal_position;
    """)
    
    print("\nTracked Deals table structure:")
    if not table_info:
        print("Table 'tracked_deals' does not exist!")
    else:
        for col in table_info:
            details = []
            if col['character_maximum_length']:
                details.append(f"max_length={col['character_maximum_length']}")
            if col['numeric_precision']:
                details.append(f"precision={col['numeric_precision']}")
            if col['numeric_scale']:
                details.append(f"scale={col['numeric_scale']}")
            
            detail_str = f" ({', '.join(details)})" if details else ""
            print(f"- {col['column_name']}: {col['data_type']}{detail_str}")
            print(f"  nullable: {col['is_nullable']}")
            print(f"  default: {col['column_default']}")
    
    await conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "reset":
            asyncio.run(reset_db())
        elif sys.argv[1] == "version":
            asyncio.run(check_version())
    asyncio.run(check_db()) 