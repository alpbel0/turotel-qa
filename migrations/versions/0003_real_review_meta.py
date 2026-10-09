"""Real review metadata: hotel_type and stars_given on reviews (NULL for humir / mabsa).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE reviews ADD COLUMN hotel_type text")
    op.execute("ALTER TABLE reviews ADD COLUMN stars_given smallint")
    op.execute("ALTER TABLE reviews ADD CONSTRAINT ck_reviews_stars_range CHECK (stars_given BETWEEN 1 AND 5)")


def downgrade() -> None:
    op.execute("ALTER TABLE reviews DROP CONSTRAINT ck_reviews_stars_range")
    op.execute("ALTER TABLE reviews DROP COLUMN stars_given")
    op.execute("ALTER TABLE reviews DROP COLUMN hotel_type")
