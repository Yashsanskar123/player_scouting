"""Idempotent, additive schema upgrades for databases created before a feature existed.

Only ever ADDS (nullable columns, new tables). Nothing is dropped or rewritten, so it is
safe to run on every start-up and on a database that already holds shortlists and notes.
"""
from __future__ import annotations

from contextlib import nullcontext

from sqlalchemy import Connection, inspect, text

from src.db.models import Base, EntryEvent

WORKFLOW_COLUMNS = {"owner": "VARCHAR(64)", "due_date": "DATE", "next_action": "VARCHAR(255)"}


def ensure_workflow_schema(bind) -> dict:
    """Add owner/due_date/next_action to shortlist_entries and create entry_events if missing.

    `bind` may be an Engine (start-up) or an open Connection (inside an Alembic migration's transaction).
    """
    added: list[str] = []
    Base.metadata.create_all(bind, tables=[EntryEvent.__table__], checkfirst=True)
    insp = inspect(bind)
    if "shortlist_entries" in insp.get_table_names():
        existing = {c["name"] for c in insp.get_columns("shortlist_entries")}
        missing = {c: ddl for c, ddl in WORKFLOW_COLUMNS.items() if c not in existing}
        if missing:
            scope = nullcontext(bind) if isinstance(bind, Connection) else bind.begin()
            with scope as conn:
                for column, ddl in missing.items():
                    conn.execute(text(f"ALTER TABLE shortlist_entries ADD COLUMN {column} {ddl}"))
                    added.append(column)
    return {"columns_added": added}
