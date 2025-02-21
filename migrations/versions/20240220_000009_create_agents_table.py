"""Create agents table.

Revision ID: 20240220_000009
Revises: 20240220_000008
Create Date: 2024-02-20 00:00:09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = '20240220_000009'
down_revision: Union[str, None] = '20240220_000008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create agents table
    op.create_table(
        'agents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', UUID(as_uuid=True), sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('agent_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='inactive'),
        sa.Column('description', sa.Text),
        sa.Column('config', JSONB),
        sa.Column('meta_data', JSONB),
        sa.Column('error_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text),
        sa.Column('last_active', sa.DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=text('CURRENT_TIMESTAMP'), onupdate=text('CURRENT_TIMESTAMP'))
    )

    # Create indexes
    op.create_index('ix_agents_type', 'agents', ['agent_type'])
    op.create_index('ix_agents_status', 'agents', ['status'])
    op.create_index('ix_agents_user', 'agents', ['user_id'])
    op.create_index('ix_agents_goal', 'agents', ['goal_id'])

    # Add check constraints for valid values
    op.execute("""
        ALTER TABLE agents 
        ADD CONSTRAINT chk_agent_type 
        CHECK (agent_type IN ('goal', 'market', 'price', 'chat'));
    """)

    op.execute("""
        ALTER TABLE agents 
        ADD CONSTRAINT chk_agent_status 
        CHECK (status IN ('active', 'inactive', 'busy', 'error'));
    """)

def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_agents_type')
    op.drop_index('ix_agents_status')
    op.drop_index('ix_agents_user')
    op.drop_index('ix_agents_goal')

    # Drop table
    op.drop_table('agents')