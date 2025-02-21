"""Create token_wallets table.

Revision ID: 20240220_000012
Revises: 20240220_000011
Create Date: 2024-02-20 00:00:12.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20240220_000012'
down_revision = '20240220_000011'
branch_labels = None
depends_on = None

def upgrade():
    # Create token_wallets table
    op.create_table(
        'token_wallets',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('address', sa.String(length=44), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_used', sa.DateTime(timezone=True), nullable=True),
        sa.Column('network', sa.String(length=20), nullable=False, server_default=sa.text("'mainnet-beta'")),
        sa.Column('data', JSONB(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('address', 'network', name='uq_wallet_address_network')
    )

    # Create indexes
    op.create_index('ix_token_wallets_user_id', 'token_wallets', ['user_id'])
    op.create_index('ix_token_wallets_address', 'token_wallets', ['address'])
    op.create_index('ix_token_wallets_network', 'token_wallets', ['network'])

def downgrade():
    # Drop indexes
    op.drop_index('ix_token_wallets_network')
    op.drop_index('ix_token_wallets_address')
    op.drop_index('ix_token_wallets_user_id')
    
    # Drop table
    op.drop_table('token_wallets') 