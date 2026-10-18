"""Baseline: the schema as of this release.

Creates any table that does not exist yet (checkfirst), so it is safe on an empty database AND on an
older database created before Alembic was introduced. Later changes must be explicit new revisions.

Revision ID: 0001
Revises:
"""
from alembic import op

from src.db.models import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise NotImplementedError("ScoutIQ migrations are additive; restore from a backup instead of downgrading.")
