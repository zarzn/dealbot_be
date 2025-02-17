"""Add auth_tokens table

Revision ID: 2025021620550
Revises: 2025021620500
Create Date: 2025-02-16 20:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '2025021620550'
down_revision: Union[str, None] = '2025021620500'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create auth_tokens table
    op.execute("""
        CREATE TABLE auth_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(255) NOT NULL UNIQUE,
            token_type VARCHAR(20) NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            scope VARCHAR(20) DEFAULT 'full',
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            meta_data JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT ch_valid_token_type CHECK (token_type IN ('access', 'refresh', 'magic_link', 'api_key')),
            CONSTRAINT ch_valid_status CHECK (status IN ('active', 'revoked', 'expired')),
            CONSTRAINT ch_valid_scope CHECK (scope IN ('full', 'read', 'write', 'admin'))
        );
        CREATE INDEX ix_auth_tokens_user ON auth_tokens(user_id);
        CREATE INDEX ix_auth_tokens_token ON auth_tokens(token);
        CREATE INDEX ix_auth_tokens_status ON auth_tokens(status);
    """)

def downgrade() -> None:
    # Drop auth_tokens table
    op.execute("DROP TABLE IF EXISTS auth_tokens CASCADE;") 