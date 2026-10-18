import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.app import app
from src.auth import permissions, security, service
from src.db.models import AuditLog, Base
from src.db.session import get_session
from src.services import data_store

SECRET = "x" * 40
PW = "correct-horse-battery"


# ---------------------------------------------------------------- unit ----
def test_password_hash_roundtrip_and_salting():
    h1, h2 = security.hash_password(PW), security.hash_password(PW)
    assert h1 != h2 and security.verify_password(PW, h1)
    assert not security.verify_password("wrong-password!", h1)
    assert not security.verify_password(PW, "garbage")


def test_token_roundtrip_tamper_and_expiry(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_AUTH_SECRET", SECRET)
    token = security.create_token("alice", now=1_000_000)
    assert security.verify_token(token, now=1_000_100)["sub"] == "alice"
    assert security.verify_token(token, now=1_000_000 + 10 * 3600) is None  # expired
    head, sig = token.split(".")
    assert security.verify_token(f"{head}.{'A' * len(sig)}") is None  # bad signature
    monkeypatch.setenv("SCOUTIQ_AUTH_SECRET", "y" * 40)
    assert security.verify_token(token, now=1_000_100) is None  # different secret


def test_missing_secret_fails_fast_only_when_enabled(monkeypatch):
    monkeypatch.delenv("SCOUTIQ_AUTH_SECRET", raising=False)
    monkeypatch.setenv("SCOUTIQ_AUTH_MODE", "off")
    security.validate_auth_config()
    monkeypatch.setenv("SCOUTIQ_AUTH_MODE", "on")
    with pytest.raises(security.AuthConfigError):
        security.validate_auth_config()


@pytest.mark.parametrize("method,path,perm", [
    ("GET", "/health", "public"), ("POST", "/api/auth/login", "public"),
    ("GET", "/api/players/abc", "read"), ("POST", "/api/squads/optimize", "read"),
    ("POST", "/api/recruitment/shortlists", "write_scouting"),
    ("PATCH", "/api/recruitment/entries/5", "write_scouting"),
    ("PUT", "/api/club-profile", "write_club"), ("POST", "/api/club-profile/activate", "write_club"), ("POST", "/api/admin/reload", "admin"),
    ("GET", "/api/audit-log", "admin"), ("DELETE", "/api/anything-new", "admin"),
])
def test_classifier(method, path, perm):
    assert permissions.classify(method, path).permission == perm


def test_role_matrix():
    assert permissions.role_allows("analyst", "read") and not permissions.role_allows("analyst", "write_scouting")
    assert permissions.role_allows("scout", "write_scouting") and not permissions.role_allows("scout", "write_club")
    assert permissions.role_allows("director", "write_club") and not permissions.role_allows("director", "admin")
    assert all(permissions.role_allows("admin", p) for p in ("read", "write_scouting", "write_club", "admin"))


# ----------------------------------------------------------------- API ----
@pytest.fixture()
def env():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = _override
    data_store.store._facts = pd.DataFrame({"club_name": ["Arsenal"], "season": [2425]})
    data_store.store._loaded_at = 1.0
    service.clear_failures()
    yield Session
    app.dependency_overrides.clear()
    data_store.store._facts = pd.DataFrame()
    data_store.store._loaded_at = None


@pytest.fixture()
def auth_on(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_AUTH_MODE", "on")
    monkeypatch.setenv("SCOUTIQ_AUTH_SECRET", SECRET)


def _make_users(Session):
    with Session() as s:
        for name, role in (("ada", "admin"), ("dan", "director"), ("sam", "scout"), ("ann", "analyst")):
            service.create_user(s, name, PW, role)


def _login(client, name, password=PW):
    r = client.post("/api/auth/login", json={"username": name, "password": password})
    return r, {"Authorization": f"Bearer {r.json().get('access_token')}"}


def test_off_mode_changes_nothing_but_audits_as_anonymous(env):
    client = TestClient(app)
    assert client.get("/api/auth/status").json()["auth_enabled"] is False
    assert client.post("/api/auth/login", json={"username": "a", "password": "b"}).status_code == 400
    r = client.post("/api/recruitment/shortlists", json={"name": "Targets"})
    assert r.status_code == 200
    with env() as s:
        row = s.scalars(select(AuditLog)).all()[-1]
        assert (row.username, row.action, row.status) == ("anonymous", "shortlist.create", 200)


def test_requires_login_when_enabled(env, auth_on):
    client = TestClient(app)
    assert client.get("/health").status_code == 200  # public
    assert client.get("/api/recruitment/shortlists").status_code == 401
    assert client.get("/api/recruitment/shortlists", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_roles_are_enforced(env, auth_on):
    _make_users(env)
    client = TestClient(app)
    hdr = {n: _login(client, n)[1] for n in ("ada", "dan", "sam", "ann")}
    assert client.get("/api/recruitment/shortlists", headers=hdr["ann"]).status_code == 200  # analyst reads
    assert client.post("/api/recruitment/shortlists", json={"name": "x"}, headers=hdr["ann"]).status_code == 403
    assert client.post("/api/recruitment/shortlists", json={"name": "x"}, headers=hdr["sam"]).status_code == 200
    bad = {"club_name": "Arsenal", "formation": "9-9-9"}  # reaches the handler (400) only if authorised
    assert client.put("/api/club-profile", json=bad, headers=hdr["sam"]).status_code == 403
    assert client.put("/api/club-profile", json=bad, headers=hdr["dan"]).status_code == 400
    assert client.get("/api/users", headers=hdr["dan"]).status_code == 403
    assert client.get("/api/users", headers=hdr["ada"]).status_code == 200


def test_login_failures_lockout_and_generic_message(env, auth_on):
    _make_users(env)
    client = TestClient(app)
    wrong = client.post("/api/auth/login", json={"username": "ann", "password": "not-the-password"})
    unknown = client.post("/api/auth/login", json={"username": "ghost", "password": "not-the-password"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()
    for _ in range(4):
        client.post("/api/auth/login", json={"username": "ann", "password": "not-the-password"})
    assert client.post("/api/auth/login", json={"username": "ann", "password": PW}).status_code == 429


def test_audit_trail_records_who_and_never_secrets(env, auth_on):
    _make_users(env)
    client = TestClient(app)
    _, sam = _login(client, "sam")
    client.post("/api/recruitment/shortlists", json={"name": "Wingers"}, headers=sam)
    client.post("/api/recruitment/shortlists", json={"name": "nope"}, headers=_login(client, "ann")[1])  # denied
    _, ada = _login(client, "ada")
    log = client.get("/api/audit-log?limit=50", headers=ada).json()
    actions = [(i["username"], i["action"], i["status"]) for i in log["items"]]
    assert ("sam", "shortlist.create", 200) in actions
    assert ("ann", "auth.forbidden", 403) in actions
    assert ("sam", "auth.login", 200) in actions
    assert PW not in str(log) and "Wingers" not in str(log)
    assert client.get("/api/audit-log", headers=sam).status_code == 403  # admin only
    only_sam = client.get("/api/audit-log?username=sam", headers=ada).json()
    assert only_sam["total"] >= 2 and all(i["username"] == "sam" for i in only_sam["items"])


def test_user_admin_rules(env, auth_on):
    _make_users(env)
    client = TestClient(app)
    _, ada = _login(client, "ada")
    assert client.post("/api/users", json={"username": "new.user", "password": "short", "role": "scout"}, headers=ada).status_code == 400
    assert client.post("/api/users", json={"username": "new.user", "password": PW, "role": "wizard"}, headers=ada).status_code == 400
    assert client.post("/api/users", json={"username": "new.user", "password": PW, "role": "scout"}, headers=ada).status_code == 201
    assert client.post("/api/users", json={"username": "NEW.user", "password": PW, "role": "scout"}, headers=ada).status_code == 400  # duplicate
    # the last active admin can be neither demoted nor deactivated
    assert client.patch("/api/users/ada", json={"role": "analyst"}, headers=ada).status_code == 400
    assert client.patch("/api/users/ada", json={"is_active": False}, headers=ada).status_code == 400
    # deactivation and role changes apply immediately to existing tokens
    _, sam = _login(client, "sam")
    assert client.patch("/api/users/sam", json={"is_active": False}, headers=ada).status_code == 200
    assert client.get("/api/recruitment/shortlists", headers=sam).status_code == 401
    assert _login(client, "sam")[0].status_code == 401


def test_bootstrap_admin_from_environment(env, auth_on, monkeypatch):
    monkeypatch.setenv("SCOUTIQ_BOOTSTRAP_ADMIN_USER", "root")
    monkeypatch.setenv("SCOUTIQ_BOOTSTRAP_ADMIN_PASSWORD", PW)
    client = TestClient(app)
    r, hdr = _login(client, "root")
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"
    assert client.get("/api/auth/me", headers=hdr).json()["user"]["username"] == "root"


def test_ensure_auth_tables_adds_missing_tables_to_an_older_database():
    from sqlalchemy import inspect
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[t for n, t in Base.metadata.tables.items() if n not in ("users", "audit_log")])
    assert "users" not in inspect(engine).get_table_names()
    service.ensure_auth_tables(engine)
    service.ensure_auth_tables(engine)  # idempotent
    assert {"users", "audit_log"} <= set(inspect(engine).get_table_names())


def test_server_startup_runs_ensure_auth_tables(monkeypatch):
    import src.api.app as app_module
    calls = []
    monkeypatch.setattr(app_module, "ensure_auth_tables", lambda: calls.append(1))
    monkeypatch.setattr(app_module, "warm_caches", lambda: calls.append("warm"))
    with TestClient(app_module.app):
        pass
    assert calls == [1, "warm"]


def test_browser_preflight_allows_authorization_header(env, auth_on):
    client = TestClient(app)
    r = client.options("/api/recruitment/shortlists", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200  # preflight is answered before authentication
    assert "authorization" in r.headers["access-control-allow-headers"].lower()


def test_exports_are_audited_and_open_to_read_only_roles(env, auth_on):
    _make_users(env)
    client = TestClient(app)
    _, sam = _login(client, "sam")
    sl = client.post("/api/recruitment/shortlists", json={"name": "Wingers"}, headers=sam).json()
    _, ann = _login(client, "ann")  # analyst: read-only
    assert client.get(f"/api/recruitment/shortlists/{sl['id']}/export.xlsx", headers=ann).status_code == 200
    assert client.get(f"/api/recruitment/shortlists/{sl['id']}/export.xlsx").status_code == 401  # no token, no export
    _, ada = _login(client, "ada")
    items = client.get("/api/audit-log?action=export.shortlist", headers=ada).json()["items"]
    assert [(i["username"], i["entity"], i["status"]) for i in items] == [("ann", str(sl["id"]), 200)]


def test_club_switching_and_workflow_follow_the_role_matrix(env, auth_on, tmp_path, monkeypatch):
    from src.features import club_profile
    monkeypatch.setattr(club_profile, "PROFILE_PATH", tmp_path / "clubs.json")
    _make_users(env)
    client = TestClient(app)
    hdr = {n: _login(client, n)[1] for n in ("dan", "sam", "ann")}
    assert client.post("/api/club-profile/activate?club_name=Arsenal", headers=hdr["sam"]).status_code == 403   # scout: no
    assert client.post("/api/club-profile/activate?club_name=Arsenal", headers=hdr["dan"]).status_code == 404   # director: allowed (club unknown)
    sl = client.post("/api/recruitment/shortlists", json={"name": "W"}, headers=hdr["sam"]).json()
    assert client.get("/api/recruitment/tasks", headers=hdr["ann"]).status_code == 200                           # analyst can read tasks
    assert client.patch("/api/recruitment/entries/1", json={"owner": "x"}, headers=hdr["ann"]).status_code == 403  # but not edit them
    assert sl["id"]
