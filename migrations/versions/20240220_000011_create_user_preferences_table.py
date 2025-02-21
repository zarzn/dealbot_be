"""Create user preferences table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20240220_000011'
down_revision = '20240220_000010'
branch_labels = None
depends_on = None

def upgrade():
    """Create user_preferences table."""
    op.create_table(
        'user_preferences',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('theme', sa.String(), nullable=False, server_default='system'),
        sa.Column('language', sa.String(), nullable=False, server_default='en'),
        sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
        sa.Column('enabled_channels', ARRAY(sa.String()), nullable=False, server_default=text("ARRAY['in_app', 'email']")),
        sa.Column('notification_frequency', JSONB(), nullable=False, server_default=text("""
            '{"deal_match": "immediate", 
              "goal_completed": "immediate", 
              "goal_expired": "daily", 
              "price_drop": "immediate", 
              "token_low": "daily", 
              "system": "immediate", 
              "custom": "immediate"}'::jsonb
        """)),
        sa.Column('time_windows', JSONB(), nullable=False, server_default=text("""
            '{"in_app": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"},
              "email": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"}}'::jsonb
        """)),
        sa.Column('muted_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('do_not_disturb', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_digest', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('push_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sms_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('telegram_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('discord_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('minimum_priority', sa.String(10), nullable=False, server_default='low'),
        sa.Column('deal_alert_settings', JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
        sa.Column('price_alert_settings', JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
        sa.Column('email_preferences', JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))
    )

    # Create indexes
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'])
    op.create_index('ix_user_preferences_created_at', 'user_preferences', ['created_at'])

def downgrade():
    """Drop user_preferences table."""
    op.drop_index('ix_user_preferences_created_at', 'user_preferences')
    op.drop_index('ix_user_preferences_user_id', 'user_preferences')
    op.drop_table('user_preferences') 