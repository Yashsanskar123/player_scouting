import json
import logging

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_response_has_request_id_and_echoes_incoming():
    assert client.get("/health").headers.get("x-request-id")
    r = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert r.headers["x-request-id"] == "trace-abc-123"


def test_request_log_is_json_without_query_or_secrets(caplog):
    with caplog.at_level(logging.INFO, logger="scoutiq.request"):
        logger = logging.getLogger("scoutiq.request")
        logger.propagate = True  # let caplog capture
        try:
            client.get("/health?token=SECRET", headers={"X-API-Key": "SECRET-KEY"})
        finally:
            logger.propagate = False
    records = [r for r in caplog.records if getattr(r, "fields", None)]
    assert records, "expected a request log record"
    fields = records[-1].fields
    assert fields["method"] == "GET" and fields["path"] == "/health" and fields["status"] == 200
    assert "duration_ms" in fields and fields["request_id"]
    text = json.dumps(fields)
    assert "SECRET" not in text
