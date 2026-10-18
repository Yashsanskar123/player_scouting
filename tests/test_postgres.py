"""PostgreSQL integration tests. Skipped unless DATABASE_URL points at a PostgreSQL database.

  DATABASE_URL=postgresql+psycopg://user:pass@host/db python -m pytest tests/test_postgres.py

These run in CI against a real PostgreSQL service. They WIPE the target database's ScoutIQ tables, so
only point them at a disposable database.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL", "").startswith("postgresql"), reason="needs a PostgreSQL DATABASE_URL")

if os.getenv("DATABASE_URL", "").startswith("postgresql"):
    from fastapi.testclient import TestClient
    from sqlalchemy import inspect, text

    from src.api.app import app
    from src.auth import service
    from src.db import migrate_cli
    from src.db.session import Base, engine

PASSWORD = "postgres-test-password"


@pytest.fixture()
def pg(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_AUTH_MODE", "on")
    monkeypatch.setenv("SCOUTIQ_AUTH_SECRET", "p" * 48)
    service.clear_failures()
    with engine.begin() as conn:  # start from nothing, then migrate exactly as a deployment would
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.drop_all(engine)
    with engine.connect() as conn:
        migrate_cli.upgrade(conn)
        conn.commit()
    import pandas as pd
    from sqlalchemy.orm import Session
    from src.db.models import PlayerIdentity
    from src.services import data_store
    with Session(engine) as s:
        for name, role in (("ada", "admin"), ("sam", "scout")):
            service.create_user(s, name, PASSWORD, role)
        s.add(PlayerIdentity(player_id="p1", identity_confidence="high", short_name="Test Player"))  # PostgreSQL enforces this foreign key
        s.commit()
    data_store.store._facts = pd.DataFrame({"player_id": ["p1"], "season": [2425], "short_name": ["Test Player"]})
    data_store.store._loaded_at = 1.0
    yield TestClient(app, raise_server_exceptions=False)
    data_store.store._facts, data_store.store._loaded_at = pd.DataFrame(), None


def _login(c, name):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"username": name, "password": PASSWORD}).json()["access_token"]}


def test_migrations_create_the_schema_on_postgresql(pg):
    insp = inspect(engine)
    assert {"shortlists", "shortlist_entries", "scout_notes", "users", "audit_log", "entry_events", "alembic_version"} <= set(insp.get_table_names())
    assert {"owner", "due_date", "next_action"} <= {c["name"] for c in insp.get_columns("shortlist_entries")}


def test_login_roles_and_audit_trail_work_on_postgresql(pg):
    ada, sam = _login(pg, "ada"), _login(pg, "sam")
    assert pg.get("/api/users", headers=sam).status_code == 403
    sl = pg.post("/api/recruitment/shortlists", json={"name": "PG list"}, headers=sam)
    assert sl.status_code == 200
    log = pg.get("/api/audit-log?limit=20", headers=ada).json()
    assert ("sam", "shortlist.create", 200) in [(i["username"], i["action"], i["status"]) for i in log["items"]]


def test_workflow_timeline_and_tasks_work_on_postgresql(pg):
    sam = _login(pg, "sam")
    sid = pg.post("/api/recruitment/shortlists", json={"name": "W"}, headers=sam).json()["id"]
    eid = pg.post(f"/api/recruitment/shortlists/{sid}/entries", json={"player_id": "p1", "status": "Monitoring"}, headers=sam).json()["id"]
    r = pg.patch(f"/api/recruitment/entries/{eid}", json={"owner": "Sam", "due_date": "2026-01-01", "next_action": "Call", "status": "Scout Review"}, headers=sam)
    assert r.status_code == 200 and r.json()["due_date"] == "2026-01-01"
    kinds = {e["kind"] for e in pg.get(f"/api/recruitment/entries/{eid}/events", headers=sam).json()["events"]}
    assert {"added", "status", "owner", "due", "next_action"} <= kinds
    tasks = pg.get("/api/recruitment/tasks", headers=sam).json()
    assert tasks["total"] == 1 and tasks["overdue"] == 1


def test_oversized_input_is_a_clean_422_not_a_database_error(pg):
    """PostgreSQL enforces column lengths (SQLite does not): these used to be 500s."""
    sam = _login(pg, "sam")
    assert pg.post("/api/recruitment/shortlists", json={"name": "x" * 500}, headers=sam).status_code == 422
    assert pg.post("/api/recruitment/players/p1/notes", json={"player_id": "p1", "note": "ok", "author": "a" * 200}, headers=sam).status_code == 422


def test_unknown_player_is_a_clean_404_not_a_foreign_key_error(pg):
    sam = _login(pg, "sam")
    sid = pg.post("/api/recruitment/shortlists", json={"name": "FK"}, headers=sam).json()["id"]
    assert pg.post(f"/api/recruitment/shortlists/{sid}/entries", json={"player_id": "ghost", "status": "Monitoring"}, headers=sam).status_code == 404
    assert pg.post(f"/api/recruitment/shortlists/{sid}/entries", json={"player_id": "p1", "status": "Monitoring"}, headers=sam).status_code == 200


def test_data_store_reads_facts_through_a_database_neutral_check(pg):
    """Regression: the store used sqlite_master, so most endpoints failed on PostgreSQL."""
    from src.services.data_store import DataStore
    store = DataStore()  # a fresh store: no fact table exists in this database yet
    store.reload()  # no fact table yet: must return empty, not raise
    assert store.facts.empty
