import pytest
from fastapi.testclient import TestClient

from src.api import hardening
from src.api.app import app
from src.api.hardening import RateLimitMiddleware

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_limiter():
    RateLimitMiddleware.reset()
    yield
    RateLimitMiddleware.reset()


def test_security_headers_on_api_and_non_api_responses():
    api = client.get("/api/auth/status")
    assert api.headers["x-content-type-options"] == "nosniff" and api.headers["x-frame-options"] == "DENY"
    assert api.headers["cache-control"] == "no-store" and "frame-ancestors 'none'" in api.headers["content-security-policy"]
    assert "strict-transport-security" not in api.headers  # only when HSTS is switched on
    health = client.get("/health")
    assert health.headers["x-content-type-options"] == "nosniff" and "content-security-policy" not in health.headers


def test_hsts_only_when_enabled(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_HSTS", "on")
    assert "max-age=31536000" in client.get("/health").headers["strict-transport-security"]


def test_oversized_bodies_get_a_clear_413(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_MAX_BODY_BYTES", "200")
    small = client.post("/api/auth/login", json={"username": "a", "password": "b"})
    assert small.status_code == 400  # login is off, but the request was accepted
    big = client.post("/api/auth/login", json={"username": "a", "password": "x" * 500})
    assert big.status_code == 413 and "too large" in big.json()["detail"]


def test_streamed_bodies_without_a_length_are_also_limited(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_MAX_BODY_BYTES", "200")
    chunks = (b'{"username":"a","password":"' + b"x" * 100 for _ in range(1)).__next__

    def stream():
        yield b'{"username":"a","password":"'
        yield b"x" * 400
        yield b'"}'

    r = client.post("/api/auth/login", content=stream(), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_rate_limit_blocks_then_reports_retry_after(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_RATE_LIMIT_PER_MINUTE", "3")
    codes = [client.get("/api/auth/status").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    blocked = client.get("/api/auth/status")
    assert int(blocked.headers["retry-after"]) >= 1 and "slow down" in blocked.json()["detail"]
    assert client.get("/health").status_code == 200  # health checks are never limited


def test_heavy_endpoints_have_their_own_tighter_limit(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_HEAVY_RATE_LIMIT_PER_MINUTE", "1")
    assert client.get("/api/players/nope/report.pdf").status_code == 404  # reaches the app
    assert client.get("/api/players/nope/report.pdf").status_code == 429
    assert client.get("/api/auth/status").status_code == 200  # ordinary traffic is unaffected


def test_limit_errors_still_carry_cors_headers_so_the_browser_can_read_them(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_RATE_LIMIT_PER_MINUTE", "1")
    origin = {"Origin": "http://localhost:3000"}
    client.get("/api/auth/status", headers=origin)
    blocked = client.get("/api/auth/status", headers=origin)
    assert blocked.status_code == 429 and blocked.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_origins_are_configurable(monkeypatch):
    assert hardening.cors_origins() == hardening.DEFAULT_ORIGINS
    monkeypatch.setenv("SCOUTIQ_CORS_ORIGINS", "https://scout.example.com/, https://b.example.com")
    assert hardening.cors_origins() == ["https://scout.example.com", "https://b.example.com"]


def test_api_key_check_is_exact(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_API_KEY", "s3cret-key")
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"X-API-Key": "s3cret-kez"}).status_code == 401
    assert client.get("/health", headers={"X-API-Key": "s3cret-key"}).status_code == 200


def test_docs_flag_parsing(monkeypatch):
    assert hardening.docs_enabled() is True
    monkeypatch.setenv("SCOUTIQ_ENABLE_DOCS", "false")
    assert hardening.docs_enabled() is False


def test_security_posture_reflects_the_environment(monkeypatch):
    for var in ("SCOUTIQ_AUTH_MODE", "SCOUTIQ_API_KEY", "SCOUTIQ_AUTH_SECRET", "SCOUTIQ_BOOTSTRAP_ADMIN_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    by = {c["key"]: c for c in hardening.security_posture()["checks"]}
    assert by["access_control"]["ok"] is False and by["access_control"]["severity"] == "high"
    monkeypatch.setenv("SCOUTIQ_AUTH_MODE", "on")
    monkeypatch.setenv("SCOUTIQ_AUTH_SECRET", "s" * 40)
    monkeypatch.setenv("SCOUTIQ_BOOTSTRAP_ADMIN_PASSWORD", "left-over-password")
    monkeypatch.setenv("SCOUTIQ_CORS_ORIGINS", "*")
    by = {c["key"]: c for c in hardening.security_posture()["checks"]}
    assert by["access_control"]["ok"] and by["auth_secret"]["ok"]
    assert by["bootstrap_password"]["ok"] is False and by["cors"]["ok"] is False and by["cors"]["severity"] == "high"


def test_posture_endpoint_is_admin_only_in_the_role_matrix():
    from src.auth.permissions import classify
    assert classify("GET", "/api/admin/security-status").permission == "admin"


def test_input_length_limits_return_clear_422s_not_server_errors():
    pid = "p" * 12
    assert client.post("/api/recruitment/shortlists", json={"name": "x" * 500}).status_code == 422
    assert client.post(f"/api/recruitment/players/{pid}/notes", json={"player_id": pid, "note": "ok", "author": "a" * 200}).status_code == 422
    assert client.post(f"/api/recruitment/players/{pid}/notes", json={"player_id": pid, "note": "n" * 20000}).status_code == 422
    assert client.patch("/api/recruitment/entries/1", json={"owner": "o" * 200}).status_code == 422
