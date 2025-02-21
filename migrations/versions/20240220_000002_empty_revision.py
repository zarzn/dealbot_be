"""Empty revision

Revision ID: 20240220_000002
Revises: 20240219_000001
Create Date: 2024-02-20 00:00:02.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20240220_000002'
down_revision: Union[str, None] = '20240219_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass 