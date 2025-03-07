"""Script to list all tables in both databases.

This script connects to both agentic_deals and agentic_deals_test databases, lists all tables,
and specifically checks for the wallet_transactions table.
"""

import asyncio
import asyncpg
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Expected tables based on migration file
EXPECTED_TABLES = [
    'users', 'auth_tokens', 'goals', 'deals', 'markets', 'price_points',
    'deal_matches', 'notifications', 'token_balances', 'token_transactions',
    'token_balance_history', 'price_histories', 'deal_scores', 'price_trackers',
    'deal_interactions', 'chat_contexts', 'tracked_deals', 'token_pricing',
    'price_predictions', 'token_wallets', 'wallet_transactions', 'chat_messages',
    'user_preferences', 'agents', 'alembic_version'
]

async def check_tables():
    """Check all tables in databases."""
    try:
        # Check both main and test databases
        for db_name in ['agentic_deals', 'agentic_deals_test']:
            # Connect to the database
            print(f"\nConnecting to the {db_name} database...")
            conn = await asyncpg.connect(
                user='postgres',
                password='12345678',
                database=db_name,
                host='localhost'
            )
            
            # Get all tables in the public schema
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            
            # Get table names as a list
            table_names = [table['table_name'] for table in tables]
            
            # Print the tables
            print(f"\nTables in {db_name} database ({len(table_names)} tables):")
            for table_name in table_names:
                print(f"- {table_name}")
            
            # Check missing tables
            missing_tables = [t for t in EXPECTED_TABLES if t not in table_names]
            if missing_tables:
                print(f"\nMISSING TABLES in {db_name} ({len(missing_tables)} tables):")
                for table_name in missing_tables:
                    print(f"- {table_name}")
            else:
                print(f"\nAll expected tables exist in {db_name}")
            
            # Specifically check for wallet_transactions
            if 'wallet_transactions' in table_names:
                print(f"\n✅ wallet_transactions table EXISTS in {db_name}")
                
                # Get column names for wallet_transactions
                columns = await conn.fetch("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'wallet_transactions'
                    ORDER BY ordinal_position;
                """)
                
                print("\nColumns in wallet_transactions table:")
                for col in columns:
                    print(f"- {col['column_name']} ({col['data_type']}, {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
            else:
                print(f"\n❌ wallet_transactions table DOES NOT EXIST in {db_name}")
            
            # Close the connection
            await conn.close()
            print(f"Connection to {db_name} closed.")
        
    except Exception as e:
        logger.error(f"Error checking database: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(check_tables()) 