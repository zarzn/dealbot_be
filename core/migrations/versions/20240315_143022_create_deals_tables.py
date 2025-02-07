"""create deals tables

Revision ID: 20240315_143022
Revises: 20240315_142022
Create Date: 2024-03-15 14:30:22.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '20240315_143022'
down_revision = '20240315_142022'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create deals table
    op.create_table(
        'deals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('original_price', sa.Numeric(10, 2)),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('image_url', sa.Text),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('deal_metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('price_metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('score', sa.Float),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('price >= 0', name='check_price_positive'),
        sa.CheckConstraint('original_price >= price', name='check_original_price_greater'),
        sa.Index('idx_deals_goal_id', 'goal_id'),
        sa.Index('idx_deals_status', 'status'),
        sa.Index('idx_deals_source', 'source'),
        sa.Index('idx_deals_created_at', 'created_at'),
        sa.Index('idx_deals_price', 'price'),
        sa.Index('idx_deals_score', 'score'),
        sa.Index('idx_deals_title_trgm', 'title', postgresql_using='gin', postgresql_ops={'title': 'gin_trgm_ops'}),
        sa.Index('idx_deals_description_trgm', 'description', postgresql_using='gin', postgresql_ops={'description': 'gin_trgm_ops'})
    )
    
    # Create deal_scores table for historical scoring
    op.create_table(
        'deal_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_name', sa.String(255), nullable=False),
        sa.Column('score', sa.Float, nullable=False),
        sa.Column('moving_average', sa.Float, nullable=False),
        sa.Column('std_dev', sa.Float, nullable=False),
        sa.Column('is_anomaly', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Index('idx_deal_scores_product_name', 'product_name'),
        sa.Index('idx_deal_scores_created_at', 'created_at')
    )
    
    # Create price_history table
    op.create_table(
        'price_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('deal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Index('idx_price_history_deal_id', 'deal_id'),
        sa.Index('idx_price_history_timestamp', 'timestamp')
    )
    
    # Create deal_analysis table
    op.create_table(
        'deal_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('deal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Float, nullable=False),
        sa.Column('metrics', postgresql.JSONB, nullable=False),
        sa.Column('analysis_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('anomaly_score', sa.Float),
        sa.Column('recommendations', postgresql.ARRAY(sa.String), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Index('idx_deal_analysis_deal_id', 'deal_id'),
        sa.Index('idx_deal_analysis_score', 'score'),
        sa.Index('idx_deal_analysis_created_at', 'created_at')
    )
    
    # Create source_reliability table
    op.create_table(
        'source_reliability',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source', sa.String(50), nullable=False, unique=True),
        sa.Column('reliability_score', sa.Float, nullable=False),
        sa.Column('total_deals', sa.Integer, nullable=False, server_default='0'),
        sa.Column('successful_deals', sa.Integer, nullable=False, server_default='0'),
        sa.Column('failed_deals', sa.Integer, nullable=False, server_default='0'),
        sa.Column('average_price_accuracy', sa.Float),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Index('idx_source_reliability_source', 'source', unique=True),
        sa.Index('idx_source_reliability_score', 'reliability_score')
    )

def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('source_reliability')
    op.drop_table('deal_analysis')
    op.drop_table('price_history')
    op.drop_table('deal_scores')
    op.drop_table('deals') 