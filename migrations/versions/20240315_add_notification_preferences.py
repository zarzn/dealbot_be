"""Add notification preferences table

Revision ID: add_notif_prefs
Revises: 20240315_initial
Create Date: 2024-03-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_notif_prefs'
down_revision: Union[str, None] = '20240315_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create notification_preferences table
    op.create_table(
        'notification_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enabled_channels', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('notification_frequency', postgresql.JSON(), nullable=False),
        sa.Column('time_windows', postgresql.JSON(), nullable=False),
        sa.Column('muted_until', sa.Time(timezone=True), nullable=True),
        sa.Column('do_not_disturb', sa.Boolean(), nullable=False, default=False),
        sa.Column('email_digest', sa.Boolean(), nullable=False, default=True),
        sa.Column('push_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('sms_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('telegram_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('discord_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('minimum_priority', sa.String(10), nullable=False, default='low'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # Create indexes
    op.create_index(
        'ix_notification_preferences_user_id',
        'notification_preferences',
        ['user_id']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_notification_preferences_user_id')

    # Drop notification_preferences table
    op.drop_table('notification_preferences') 