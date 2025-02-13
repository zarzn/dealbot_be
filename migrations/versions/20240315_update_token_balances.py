"""Update token_balances table.

Revision ID: 20240315_update_token_balances
Revises: add_notif_prefs
Create Date: 2024-03-15 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20240315_update_token_balances'
down_revision = 'add_notif_prefs'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Rename last_updated to updated_at for consistency
    op.alter_column('token_balances', 'last_updated',
                    new_column_name='updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
    
    # Add created_at column
    op.add_column('token_balances',
                  sa.Column('created_at', sa.DateTime(timezone=True),
                           server_default=sa.text('CURRENT_TIMESTAMP'),
                           nullable=False))

def downgrade() -> None:
    # Rename updated_at back to last_updated
    op.alter_column('token_balances', 'updated_at',
                    new_column_name='last_updated',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
    
    # Drop created_at column
    op.drop_column('token_balances', 'created_at') 