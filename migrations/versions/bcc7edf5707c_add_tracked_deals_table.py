"""add tracked_deals table

Revision ID: bcc7edf5707c
Revises: 20240220_000002
Create Date: 2024-02-20 13:47:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'bcc7edf5707c'
down_revision: Union[str, None] = '20240220_000002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create tracked_deals table
    op.execute("""
        CREATE TABLE tracked_deals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            tracking_started TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_checked TIMESTAMP WITH TIME ZONE,
            last_price NUMERIC(10, 2),
            is_favorite BOOLEAN NOT NULL DEFAULT false,
            notify_on_price_drop BOOLEAN NOT NULL DEFAULT true,
            notify_on_availability BOOLEAN NOT NULL DEFAULT true,
            price_threshold NUMERIC(10, 2),
            tracking_metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX ix_tracked_deals_user ON tracked_deals(user_id);
        CREATE INDEX ix_tracked_deals_deal ON tracked_deals(deal_id);
        CREATE INDEX ix_tracked_deals_status ON tracked_deals(status);
    """)

def downgrade() -> None:
    # Drop tracked_deals table
    op.execute("DROP TABLE IF EXISTS tracked_deals CASCADE;") 