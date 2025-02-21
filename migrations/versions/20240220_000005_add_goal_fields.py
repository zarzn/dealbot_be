"""Add missing fields to goals table.

Revision ID: 20240220_000005
Revises: 20240220_000004
Create Date: 2024-02-20 00:00:05.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '20240220_000005'
down_revision = '20240220_000004'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Add missing fields to goals table."""
    # Add new columns
    op.add_column('goals', sa.Column('matches_found', sa.Integer, nullable=False, server_default='0'))
    op.add_column('goals', sa.Column('deals_processed', sa.Integer, nullable=False, server_default='0'))
    op.add_column('goals', sa.Column('tokens_spent', sa.Numeric(18, 8), nullable=False, server_default='0'))
    op.add_column('goals', sa.Column('rewards_earned', sa.Numeric(18, 8), nullable=False, server_default='0'))
    op.add_column('goals', sa.Column('last_processed_at', sa.DateTime(timezone=True)))
    op.add_column('goals', sa.Column('processing_stats', JSONB, nullable=False, server_default='{}'))
    op.add_column('goals', sa.Column('best_match_score', sa.Numeric(3, 2)))
    op.add_column('goals', sa.Column('average_match_score', sa.Numeric(3, 2)))
    op.add_column('goals', sa.Column('active_deals_count', sa.Integer, nullable=False, server_default='0'))
    op.add_column('goals', sa.Column('success_rate', sa.Numeric(3, 2), nullable=False, server_default='0'))

    # Add constraints
    op.create_check_constraint('ch_positive_tokens', 'goals', 'tokens_spent >= 0')
    op.create_check_constraint('ch_positive_rewards', 'goals', 'rewards_earned >= 0')

def downgrade() -> None:
    """Remove added fields from goals table."""
    # Drop constraints
    op.drop_constraint('ch_positive_tokens', 'goals')
    op.drop_constraint('ch_positive_rewards', 'goals')

    # Drop columns
    op.drop_column('goals', 'success_rate')
    op.drop_column('goals', 'active_deals_count')
    op.drop_column('goals', 'average_match_score')
    op.drop_column('goals', 'best_match_score')
    op.drop_column('goals', 'processing_stats')
    op.drop_column('goals', 'last_processed_at')
    op.drop_column('goals', 'rewards_earned')
    op.drop_column('goals', 'tokens_spent')
    op.drop_column('goals', 'deals_processed')
    op.drop_column('goals', 'matches_found') 