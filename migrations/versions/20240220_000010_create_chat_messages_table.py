"""Create chat_messages table.

Revision ID: 20240220_000010
Revises: 20240220_000009
Create Date: 2024-02-20 00:00:10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import text
from datetime import datetime
from uuid import uuid4

# revision identifiers, used by Alembic.
revision = '20240220_000010'
down_revision = '20240220_000009'
branch_labels = None
depends_on = None

def upgrade():
    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', UUID(), primary_key=True, nullable=False, server_default=text("gen_random_uuid()")),
        sa.Column('user_id', UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', UUID(), nullable=False),
        sa.Column('role', sa.Enum('user', 'assistant', 'system', name='messagerole', create_type=False), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='messagestatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('tokens_used', sa.Integer()),
        sa.Column('context', JSONB()),
        sa.Column('chat_metadata', JSONB()),
        sa.Column('error', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=text('NOW()'), onupdate=text('NOW()'))
    )

    # Create indexes
    op.create_index('ix_chat_messages_user_id', 'chat_messages', ['user_id'])
    op.create_index('ix_chat_messages_conversation_id', 'chat_messages', ['conversation_id'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])

def downgrade():
    # Drop indexes
    op.drop_index('ix_chat_messages_created_at')
    op.drop_index('ix_chat_messages_conversation_id')
    op.drop_index('ix_chat_messages_user_id')

    # Drop table
    op.drop_table('chat_messages') 