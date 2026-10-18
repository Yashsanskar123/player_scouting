"""Structured request logging with request IDs.

* One JSON log line per request: request_id, method, path, status, duration_ms.
* Honors an incoming X-Request-ID (so a gateway can correlate) or creates one,
  and always returns it in the X-Request-ID response header.
* Never logs query strings, bodies or the X-API-Key header.
* Unhandled exceptions are logged with the request id, then re-raised so
  FastAPI's normal error handling is unchanged.
Level via LOG_LEVEL (default INFO).
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

logger = logging.getLogger("scoutiq.request")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname, "logger": record.name}
        payload["message"] = record.getMessage()
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Idempotent: safe to call more than once."""
    log = logging.getLogger("scoutiq")
    if any(getattr(h, "_scoutiq", False) for h in log.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._scoutiq = True  # type: ignore[attr-defined]
    log.addHandler(handler)
    log.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    log.propagate = False


class RequestLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")[:64]
        request_id = incoming or uuid.uuid4().hex[:16]
        # Shared per-request state: later middleware/dependencies read request_id and write audit info here.
        scope.setdefault("state", {})["request_id"] = request_id
        start = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = dict(message, headers=headers)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.error("unhandled exception", exc_info=True, extra={"fields": {
                "request_id": request_id, "method": scope.get("method"), "path": scope.get("path"), "status": 500}})
            raise
        finally:
            logger.info("request", extra={"fields": {
                "request_id": request_id, "method": scope.get("method"), "path": scope.get("path"),
                "status": status["code"], "duration_ms": round((time.perf_counter() - start) * 1000, 1)}})
