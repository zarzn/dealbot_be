"""Script to clean up duplicate token balances."""
from sqlalchemy import create_engine, text
import sys

def cleanup_duplicates():
    """Clean up duplicate token balances."""
    engine = create_engine('postgresql://postgres:12345678@localhost:5432/agentic_deals')
    
    with engine.begin() as conn:
        # Delete duplicates keeping only the latest record for each user
        conn.execute(text("""
            WITH duplicates AS (
                SELECT id,
                       user_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id
                           ORDER BY created_at DESC
                       ) as row_num
                FROM token_balances
            )
            DELETE FROM token_balances
            WHERE id IN (
                SELECT id
                FROM duplicates
                WHERE row_num > 1
            );
        """))

if __name__ == "__main__":
    cleanup_duplicates() 