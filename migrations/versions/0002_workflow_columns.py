"""Scout Workspace workflow: owner, due_date, next_action on shortlist_entries.

Needed for databases created before these columns existed. A no-op when they are already there.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

from src.db.migrate import ensure_workflow_schema

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ensure_workflow_schema(op.get_bind())


def downgrade() -> None:
    raise NotImplementedError("ScoutIQ migrations are additive; restore from a backup instead of downgrading.")
