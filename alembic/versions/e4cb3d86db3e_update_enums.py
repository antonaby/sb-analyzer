"""Update Enums

Revision ID: e4cb3d86db3e
Revises: f5ec7087b755
Create Date: 2025-10-15 11:24:23.675854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4cb3d86db3e'
down_revision: Union[str, Sequence[str], None] = 'f5ec7087b755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE annotation_kind RENAME VALUE 'summary' TO 'label';")
    op.execute("ALTER TYPE annotation_kind RENAME VALUE 'summary_synopsis' TO 'synopsis';")
    op.execute("ALTER TYPE meta_source RENAME VALUE 'summary' TO 'topic';")
    
    # Add new value
    op.execute("ALTER TYPE annotation_kind ADD VALUE IF NOT EXISTS 'action';")


def downgrade() -> None:
    """Downgrade schema."""
    pass
