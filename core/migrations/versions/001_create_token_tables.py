"""create token tables

Revision ID: 001
Revises: 
Create Date: 2024-03-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '001'
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
            'transfer'
        )
    """)

    # Create transaction_status enum
    op.execute("""
        CREATE TYPE transaction_status AS ENUM (
            'pending',
            'completed',
            'failed',
            'cancelled'
        )
    """)

    # Create token_transactions table
    op.create_table(
        'token_transactions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.Enum('payment', 'refund', 'reward', 'transfer', name='transaction_type'), nullable=False),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('status', sa.Enum('pending', 'completed', 'failed', 'cancelled', name='transaction_status'), nullable=False, server_default='pending'),
        sa.Column('data', postgresql.JSONB, nullable=True),
        sa.Column('error', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.Column('signature', sa.String(88), nullable=True),  # Solana transaction signature
        sa.Column('slot', sa.BigInteger, nullable=True),  # Solana slot number
        sa.Column('network', sa.String(20), nullable=False, server_default='mainnet-beta'),  # Solana network
        sa.Column('fee', sa.Float, nullable=True),  # Transaction fee in SOL
        
        # Indexes
        sa.Index('ix_token_transactions_user_id', 'user_id'),
        sa.Index('ix_token_transactions_created_at', 'created_at'),
        sa.Index('ix_token_transactions_status', 'status'),
        sa.Index('ix_token_transactions_signature', 'signature', unique=True, postgresql_where=sa.text("signature IS NOT NULL"))
    )

    # Create token_prices table
    op.create_table(
        'token_prices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('price', sa.Float, nullable=False),
        sa.Column('timestamp', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('data', postgresql.JSONB, nullable=True),
        
        # Indexes
        sa.Index('ix_token_prices_timestamp', 'timestamp')
    )

    # Create token_balances table
    op.create_table(
        'token_balances',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('balance', sa.Float, nullable=False, server_default='0'),
        sa.Column('last_updated', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('data', postgresql.JSONB, nullable=True),
        
        # Indexes
        sa.Index('ix_token_balances_user_id', 'user_id', unique=True)
    )

    # Create token_wallets table
    op.create_table(
        'token_wallets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('address', sa.String(44), nullable=False),  # Solana address length
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_used', sa.DateTime, nullable=True),
        sa.Column('network', sa.String(20), nullable=False, server_default='mainnet-beta'),  # Solana network
        sa.Column('data', postgresql.JSONB, nullable=True),
        
        # Indexes
        sa.Index('ix_token_wallets_user_id', 'user_id'),
        sa.Index('ix_token_wallets_address', 'address', unique=True)
    )

    # Add constraints
    op.create_check_constraint(
        'ck_token_transactions_amount_positive',
        'token_transactions',
        'amount > 0'
    )

    op.create_check_constraint(
        'ck_token_prices_price_positive',
        'token_prices',
        'price >= 0'
    )

    op.create_check_constraint(
        'ck_token_balances_balance_non_negative',
        'token_balances',
        'balance >= 0'
    )

    # Add network constraints
    op.create_check_constraint(
        'ck_token_transactions_network',
        'token_transactions',
        "network IN ('mainnet-beta', 'testnet', 'devnet')"
    )

    op.create_check_constraint(
        'ck_token_wallets_network',
        'token_wallets',
        "network IN ('mainnet-beta', 'testnet', 'devnet')"
    )

def downgrade() -> None:
    # Drop tables
    op.drop_table('token_wallets')
    op.drop_table('token_balances')
    op.drop_table('token_prices')
    op.drop_table('token_transactions')

    # Drop enums
    op.execute('DROP TYPE transaction_status')
    op.execute('DROP TYPE transaction_type')