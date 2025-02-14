"""add_price_tracking_and_prediction_tables

Revision ID: 05c42bf802a6
Revises: 20240315_update_token_balances
Create Date: 2025-02-13 12:00:21.710815+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "05c42bf802a6"
down_revision: Union[str, None] = "20240315_update_token_balances"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create price_points table
    op.create_table(
        'price_points',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('deal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(), server_default='USD', nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_points_id'), 'price_points', ['id'], unique=False)
    op.create_index(op.f('ix_price_points_deal_id'), 'price_points', ['deal_id'], unique=False)
    op.create_index(op.f('ix_price_points_timestamp'), 'price_points', ['timestamp'], unique=False)

    # Create price_trackers table
    op.create_table(
        'price_trackers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('deal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('initial_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('threshold_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('check_interval', sa.Integer(), server_default='300', nullable=False),
        sa.Column('last_check', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notification_settings', postgresql.JSONB(), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_trackers_id'), 'price_trackers', ['id'], unique=False)
    op.create_index(op.f('ix_price_trackers_deal_id'), 'price_trackers', ['deal_id'], unique=False)
    op.create_index(op.f('ix_price_trackers_user_id'), 'price_trackers', ['user_id'], unique=False)
    op.create_index(op.f('ix_price_trackers_is_active'), 'price_trackers', ['is_active'], unique=False)

    # Create price_predictions table
    op.create_table(
        'price_predictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('deal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_name', sa.String(), nullable=False),
        sa.Column('prediction_days', sa.Integer(), server_default='7', nullable=False),
        sa.Column('confidence_threshold', sa.Float(), server_default='0.8', nullable=False),
        sa.Column('predictions', postgresql.JSONB(), nullable=False),
        sa.Column('overall_confidence', sa.Float(), nullable=False),
        sa.Column('trend_direction', sa.String(), nullable=True),
        sa.Column('trend_strength', sa.Float(), nullable=True),
        sa.Column('seasonality_score', sa.Float(), nullable=True),
        sa.Column('features_used', postgresql.JSONB(), nullable=True),
        sa.Column('model_params', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_predictions_id'), 'price_predictions', ['id'], unique=False)
    op.create_index(op.f('ix_price_predictions_deal_id'), 'price_predictions', ['deal_id'], unique=False)
    op.create_index(op.f('ix_price_predictions_user_id'), 'price_predictions', ['user_id'], unique=False)
    op.create_index(op.f('ix_price_predictions_model_name'), 'price_predictions', ['model_name'], unique=False)

    # Create model_metrics table
    op.create_table(
        'model_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(), nullable=False),
        sa.Column('accuracy', sa.Float(), nullable=False),
        sa.Column('mae', sa.Float(), nullable=False),
        sa.Column('mse', sa.Float(), nullable=False),
        sa.Column('rmse', sa.Float(), nullable=False),
        sa.Column('mape', sa.Float(), nullable=False),
        sa.Column('r2_score', sa.Float(), nullable=False),
        sa.Column('training_time', sa.Float(), nullable=True),
        sa.Column('prediction_time', sa.Float(), nullable=True),
        sa.Column('last_retrain', sa.DateTime(), nullable=False),
        sa.Column('feature_importance', postgresql.JSONB(), nullable=True),
        sa.Column('meta_data', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_metrics_id'), 'model_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_model_metrics_model_name'), 'model_metrics', ['model_name'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('model_metrics')
    op.drop_table('price_predictions')
    op.drop_table('price_trackers')
    op.drop_table('price_points')
