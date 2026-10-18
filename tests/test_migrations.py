import sqlite3

import pytest
from sqlalchemy import create_engine, inspect, text

from src.db import migrate_cli

WORKFLOW = {"owner", "due_date", "next_action"}
LEGACY_ENTRIES = (
    "create table shortlist_entries (id integer primary key, shortlist_id int, player_id text, status text, notes text, rating int, added_at text)"
)


def _tables(engine):
    return set(inspect(engine).get_table_names())


def test_upgrade_builds_the_full_schema_on_an_empty_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    with engine.connect() as conn:
        migrate_cli.upgrade(conn)
        conn.commit()
    assert {"shortlists", "shortlist_entries", "scout_notes", "users", "audit_log", "entry_events", "alembic_version"} <= _tables(engine)
    assert WORKFLOW <= {c["name"] for c in inspect(engine).get_columns("shortlist_entries")}
    with engine.connect() as conn:
        assert conn.execute(text("select version_num from alembic_version")).scalar() == "0002"


def test_upgrade_keeps_the_data_in_a_database_created_before_migrations_existed(tmp_path):
    path = tmp_path / "legacy.db"
    con = sqlite3.connect(path)
    con.execute("create table shortlists (id integer primary key, name text, created_at text)")
    con.execute(LEGACY_ENTRIES)
    con.execute("insert into shortlists values (1, 'Old list', '2026-01-01')")
    con.execute("insert into shortlist_entries values (1, 1, 'p1', 'Monitoring', 'kept note', 4, '2026-01-02')")
    con.commit()
    con.close()
    engine = create_engine(f"sqlite:///{path}")
    for _ in range(2):  # the second run must change nothing and not fail
        with engine.connect() as conn:
            migrate_cli.upgrade(conn)
            conn.commit()
    assert WORKFLOW <= {c["name"] for c in inspect(engine).get_columns("shortlist_entries")}
    with engine.connect() as conn:
        assert conn.execute(text("select status, notes, rating, owner from shortlist_entries")).fetchone() == ("Monitoring", "kept note", 4, None)
        assert conn.execute(text("select name from shortlists")).scalar() == "Old list"


def test_downgrades_are_refused_on_purpose():
    from importlib import import_module
    with pytest.raises(NotImplementedError):
        import_module("migrations.versions.0001_baseline").downgrade()
