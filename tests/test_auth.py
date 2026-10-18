import importlib
import os

import pytest
from fastapi.testclient import TestClient


def _fresh_app():
    """Re-import the app module so it picks up the current
    SCOUTIQ_API_KEY env var at construction time (app.py reads it once
    when the module loads, via the auth dependency)."""
    import src.api.app as app_module
    importlib.reload(app_module)
    return app_module.app


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SCOUTIQ_API_KEY", raising=False)
    client = TestClient(_fresh_app())
    resp = client.get("/health")
    assert resp.status_code == 200


def test_auth_rejects_missing_key_when_configured(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_API_KEY", "test-secret-key")
    client = TestClient(_fresh_app())
    resp = client.get("/health")
    assert resp.status_code == 401


def test_auth_rejects_wrong_key_when_configured(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_API_KEY", "test-secret-key")
    client = TestClient(_fresh_app())
    resp = client.get("/health", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


def test_auth_accepts_correct_key_when_configured(monkeypatch):
    monkeypatch.setenv("SCOUTIQ_API_KEY", "test-secret-key")
    client = TestClient(_fresh_app())
    resp = client.get("/health", headers={"X-API-Key": "test-secret-key"})
    assert resp.status_code == 200


@pytest.fixture(autouse=True)
def _reset_app_after_each_test():
    yield
    # Reload once more after each test with no env var set, so later test
    # files (which import `app` expecting auth disabled) aren't left
    # pointed at an app instance still requiring a key from a prior test.
    os.environ.pop("SCOUTIQ_API_KEY", None)
    _fresh_app()
