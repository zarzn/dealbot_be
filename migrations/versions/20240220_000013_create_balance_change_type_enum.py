"""Create balance change type enum.

Revision ID: 20240220_000013
Revises: 20240220_000012
Create Date: 2024-02-20 00:00:13.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '20240220_000013'
down_revision = '20240220_000012'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Create balance change type enum."""
    # Create the enum type
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE balancechangetype AS ENUM ('deduction', 'reward', 'refund');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

def downgrade() -> None:
    """Drop balance change type enum."""
    op.execute("""
        DROP TYPE IF EXISTS balancechangetype;
    """) 