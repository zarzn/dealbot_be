"""Update token_balance_history table.

Revision ID: 20240220_000008
Revises: 20240220_000007
Create Date: 2024-02-20 00:00:08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = '20240220_000008'
down_revision: Union[str, None] = '20240220_000007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def has_column(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    query = text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name=:table_name AND column_name=:column_name)"
    )
    return conn.execute(query, {"table_name": table_name, "column_name": column_name}).scalar()

def upgrade() -> None:
    # Add updated_at column with trigger
    if not has_column('token_balance_history', 'updated_at'):
        op.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """)
        
        op.add_column('token_balance_history',
            sa.Column('updated_at', sa.DateTime(timezone=True),
                     nullable=False,
                     server_default=sa.text('CURRENT_TIMESTAMP'))
        )
        
        op.execute("""
            CREATE TRIGGER update_token_balance_history_updated_at
                BEFORE UPDATE ON token_balance_history
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """)

def downgrade() -> None:
    # Drop trigger and function first
    op.execute("DROP TRIGGER IF EXISTS update_token_balance_history_updated_at ON token_balance_history")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    
    # Drop column
    if has_column('token_balance_history', 'updated_at'):
        op.drop_column('token_balance_history', 'updated_at') 