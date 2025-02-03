"""Create token tables.

Revision ID: 20240315_001
Revises: 
Create Date: 2024-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20240315_001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create transaction_type enum
    op.execute("""
        CREATE TYPE transaction_type AS ENUM (
            'payment',
            'refund',
            'reward',
            'search_payment',
            'search_refund'
        )
    """)
    
    # Create transaction_status enum
    op.execute("""
        CREATE TYPE transaction_status AS ENUM (
            'pending',
            'completed',
            'failed',
            'refunded'
        )
    """)
    
    # Create token_balances table
    op.create_table(
        'token_balances',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('balance', sa.DECIMAL(precision=18, scale=8), nullable=False, server_default=sa.text('0')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create token_transactions table
    op.create_table(
        'token_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.Enum('payment', 'refund', 'reward', 'search_payment', 'search_refund', name='transaction_type'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'completed', 'failed', 'refunded', name='transaction_status'), nullable=False, server_default='pending'),
        sa.Column('amount', sa.DECIMAL(precision=18, scale=8), nullable=False),
        sa.Column('balance_before', sa.DECIMAL(precision=18, scale=8), nullable=False),
        sa.Column('balance_after', sa.DECIMAL(precision=18, scale=8), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('signature', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(
        'ix_token_balances_user_id',
        'token_balances',
        ['user_id']
    )
    op.create_index(
        'ix_token_transactions_user_id',
        'token_transactions',
        ['user_id']
    )
    op.create_index(
        'ix_token_transactions_created_at',
        'token_transactions',
        ['created_at']
    )
    op.create_index(
        'ix_token_transactions_status',
        'token_transactions',
        ['status']
    )

def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_token_transactions_status')
    op.drop_index('ix_token_transactions_created_at')
    op.drop_index('ix_token_transactions_user_id')
    op.drop_index('ix_token_balances_user_id')
    
    # Drop tables
    op.drop_table('token_transactions')
    op.drop_table('token_balances')
    
    # Drop enums
    op.execute('DROP TYPE transaction_status')
    op.execute('DROP TYPE transaction_type') 