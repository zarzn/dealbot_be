"""Add deal_source enum type and update deals table.

Revision ID: 20240220_000006
Revises: 20240220_000005
Create Date: 2024-02-20 00:00:06.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = '20240220_000006'
down_revision = '20240220_000005'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Add deal_source enum type and update deals table."""
    # Create deal_source enum type
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deal_source AS ENUM ('manual', 'api', 'scraper', 'user', 'agent');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create a temporary column with the new enum type
    op.add_column('deals', sa.Column('source_new', ENUM('manual', 'api', 'scraper', 'user', 'agent', name='deal_source')))
    
    # Copy data from old source column to new source column
    op.execute("""
        UPDATE deals
        SET source_new = source::deal_source
        WHERE source IS NOT NULL;
    """)
    
    # Drop old source column and rename new column
    op.drop_column('deals', 'source')
    op.alter_column('deals', 'source_new', new_column_name='source')

def downgrade() -> None:
    """Revert changes."""
    # Create a temporary VARCHAR column
    op.add_column('deals', sa.Column('source_old', sa.String(50)))
    
    # Copy data from enum column to varchar column
    op.execute("""
        UPDATE deals
        SET source_old = source::text
        WHERE source IS NOT NULL;
    """)
    
    # Drop enum column and rename varchar column
    op.drop_column('deals', 'source')
    op.alter_column('deals', 'source_old', new_column_name='source')
    
    # Drop the enum type
    op.execute('DROP TYPE IF EXISTS deal_source;') 