"""add user status enum

Revision ID: 20240315_002
Revises: 20240315_001_create_token_tables
Create Date: 2024-03-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20240315_002'
down_revision: Union[str, None] = '20240315_001_create_token_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create enum type
    userstatus = postgresql.ENUM('active', 'inactive', 'suspended', 'deleted', name='userstatus')
    userstatus.create(op.get_bind())

    # Add status column with enum type
    op.add_column('users', sa.Column('status', userstatus, nullable=False, server_default='active'))

def downgrade() -> None:
    # Drop status column
    op.drop_column('users', 'status')
    
    # Drop enum type
    userstatus = postgresql.ENUM('active', 'inactive', 'suspended', 'deleted', name='userstatus')
    userstatus.drop(op.get_bind()) 