"""Script to add unique constraint to token_balances table."""
from sqlalchemy import create_engine, text
import sys

def add_unique_constraint():
    """Add unique constraint to token_balances table."""
    engine = create_engine('postgresql://postgres:12345678@localhost:5432/agentic_deals')
    
    with engine.begin() as conn:
        # First drop the constraint if it exists
        conn.execute(text("""
            DO $$ 
            BEGIN
                ALTER TABLE token_balances DROP CONSTRAINT IF EXISTS uq_token_balances_user_id;
            EXCEPTION WHEN undefined_object THEN
                NULL;
            END $$;
        """))
        
        # Add the unique constraint
        conn.execute(text("""
            ALTER TABLE token_balances 
            ADD CONSTRAINT uq_token_balances_user_id 
            UNIQUE (user_id);
        """))

if __name__ == "__main__":
    add_unique_constraint() 