"""Add missing fields to notifications table.

Revision ID: 20240220_000007
Revises: 20240220_000006
Create Date: 2024-02-20 00:00:07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = '20240220_000007'
down_revision: Union[str, None] = '20240220_000006'
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
    # Add columns if they don't exist
    if not has_column('notifications', 'notification_metadata'):
        op.add_column('notifications', sa.Column('notification_metadata', JSONB))
    
    if not has_column('notifications', 'expires_at'):
        op.add_column('notifications', sa.Column('expires_at', sa.DateTime(timezone=True)))
    
    if not has_column('notifications', 'schedule_for'):
        op.add_column('notifications', sa.Column('schedule_for', sa.DateTime(timezone=True)))
    
    if not has_column('notifications', 'error'):
        op.add_column('notifications', sa.Column('error', sa.Text))
    
    if not has_column('notifications', 'retry_count'):
        op.add_column('notifications', sa.Column('retry_count', sa.Integer, server_default='0'))
    
    if not has_column('notifications', 'max_retries'):
        op.add_column('notifications', sa.Column('max_retries', sa.Integer, server_default='3'))

    # Create index for scheduled notifications if it doesn't exist
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = 'notifications' "
        "AND indexname = 'ix_notifications_schedule_status')"
    )).scalar()
    
    if not result:
        op.create_index(
            'ix_notifications_schedule_status',
            'notifications',
            ['schedule_for', 'status']
        )

def downgrade() -> None:
    # Drop index if exists
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = 'notifications' "
        "AND indexname = 'ix_notifications_schedule_status')"
    )).scalar()
    
    if result:
        op.drop_index('ix_notifications_schedule_status', table_name='notifications')

    # Drop columns if they exist
    if has_column('notifications', 'max_retries'):
        op.drop_column('notifications', 'max_retries')
    
    if has_column('notifications', 'retry_count'):
        op.drop_column('notifications', 'retry_count')
    
    if has_column('notifications', 'error'):
        op.drop_column('notifications', 'error')
    
    if has_column('notifications', 'schedule_for'):
        op.drop_column('notifications', 'schedule_for')
    
    if has_column('notifications', 'expires_at'):
        op.drop_column('notifications', 'expires_at')
    
    if has_column('notifications', 'notification_metadata'):
        op.drop_column('notifications', 'notification_metadata') 