"""Production hardening: security headers, request size limit, rate limiting, posture check.

Everything is configured by environment variables and defaults to values that cannot break a
normal browser session or the test suite:
  SCOUTIQ_CORS_ORIGINS            comma-separated allowed origins        (default: localhost:3000)
  SCOUTIQ_ENABLE_DOCS             true/false: serve /docs and /openapi.json   (default: true)
  SCOUTIQ_MAX_BODY_BYTES          largest accepted request body          (default: 1000000)
  SCOUTIQ_RATE_LIMIT_PER_MINUTE   per client IP, 0 disables              (default: 600)
  SCOUTIQ_HEAVY_RATE_LIMIT_PER_MINUTE  exports / optimizer, per IP, 0 disables (default: 30)
  SCOUTIQ_TRUST_PROXY             on: take the client IP from X-Forwarded-For (only behind your own proxy)
  SCOUTIQ_HSTS                    on: send Strict-Transport-Security (only when served over HTTPS)
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import deque

logger = logging.getLogger("scoutiq.security")
DEFAULT_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
EXEMPT_PATHS = {"/health", "/ready"}


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _on(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "on", "yes", "enabled"}


def cors_origins() -> list[str]:
    raw = os.getenv("SCOUTIQ_CORS_ORIGINS", "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return origins or DEFAULT_ORIGINS


def docs_enabled() -> bool:
    return _on("SCOUTIQ_ENABLE_DOCS", True)


async def _send_json(send, status: int, body: dict, extra_headers: list[tuple[bytes, bytes]] | None = None) -> None:
    payload = json.dumps(body).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode()), *(extra_headers or [])]})
    await send({"type": "http.response.body", "body": payload})


def _client_ip(scope) -> str:
    if _on("SCOUTIQ_TRUST_PROXY"):
        for name, value in scope.get("headers") or []:
            if name == b"x-forwarded-for":
                return value.decode("latin-1").split(",")[0].strip()[:64] or "unknown"
    client = scope.get("client")
    return client[0] if client else "unknown"


class SecurityHeadersMiddleware:
    """Adds conservative headers to every response; never overrides one the app already set."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope.get("path", "").startswith("/api/")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                present = {k.lower() for k, _ in message.get("headers", [])}
                extra = {b"x-content-type-options": b"nosniff", b"x-frame-options": b"DENY", b"referrer-policy": b"no-referrer",
                         b"cross-origin-resource-policy": b"same-site"}
                if is_api:  # API responses carry personal/scouting data: never cache, never render as a page
                    extra[b"cache-control"] = b"no-store"
                    extra[b"content-security-policy"] = b"default-src 'none'; frame-ancestors 'none'"
                if _on("SCOUTIQ_HSTS"):
                    extra[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
                message = dict(message, headers=list(message.get("headers", [])) + [(k, v) for k, v in extra.items() if k not in present])
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Rejects oversized request bodies (413) by declared length and by bytes actually streamed."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        limit = _env_int("SCOUTIQ_MAX_BODY_BYTES", 1_000_000)
        if scope["type"] != "http" or limit == 0:
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await _send_json(send, 413, {"detail": f"Request body too large (limit {limit} bytes)."})
            return
        state = {"bytes": 0, "too_large": False, "replaced": False}
        message_413 = {"detail": f"Request body too large (limit {limit} bytes)."}

        async def counted_receive():
            message = await receive()
            if message["type"] == "http.request":
                state["bytes"] += len(message.get("body", b""))
                if state["bytes"] > limit:
                    state["too_large"] = True
                    raise BodyTooLarge()
            return message

        async def guarded_send(message):
            # The framework may turn our exception into its own 400; once the limit was exceeded, the answer is always 413.
            if state["too_large"]:
                if message["type"] == "http.response.start" and not state["replaced"]:
                    state["replaced"] = True
                    await _send_json(send, 413, message_413)
                return
            await send(message)

        try:
            await self.app(scope, counted_receive, guarded_send)
        except BodyTooLarge:
            pass
        if state["too_large"] and not state["replaced"]:
            await _send_json(send, 413, message_413)


class RateLimitMiddleware:
    """Sliding one-minute window per client IP. In-memory: per server process (use a gateway for fleets)."""

    _hits: dict[str, deque] = {}
    _lock = threading.Lock()

    def __init__(self, app):
        self.app = app

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._hits.clear()

    @staticmethod
    def _is_heavy(path: str) -> bool:
        return path.endswith((".pdf", ".xlsx")) or path == "/api/squads/optimize"

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or path in EXEMPT_PATHS or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        heavy = self._is_heavy(path)
        limit = _env_int("SCOUTIQ_HEAVY_RATE_LIMIT_PER_MINUTE", 30) if heavy else _env_int("SCOUTIQ_RATE_LIMIT_PER_MINUTE", 600)
        if limit == 0:
            await self.app(scope, receive, send)
            return
        key, now = f"{_client_ip(scope)}|{'heavy' if heavy else 'all'}", time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= 60:
                hits.popleft()
            if len(hits) >= limit:
                retry = max(1, int(60 - (now - hits[0])) + 1)
                blocked = True
            else:
                hits.append(now)
                blocked = False
            if len(self._hits) > 20000:  # bound memory under address-spraying
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= 60]:
                    del self._hits[k]
        if blocked:
            logger.warning("rate limit exceeded", extra={"fields": {"client": _client_ip(scope), "path": path, "limit": limit}})
            await _send_json(send, 429, {"detail": "Too many requests. Please slow down and retry shortly."}, [(b"retry-after", str(retry).encode())])
            return
        await self.app(scope, receive, send)


def security_posture() -> dict:
    """What a deployment is (and is not) protected against right now. Shown to admins; high items are logged at start-up."""
    from src.auth.security import auth_enabled
    from src.db.session import DATABASE_URL
    checks: list[dict] = []

    def add(key, title, ok, severity, detail):
        checks.append({"key": key, "title": title, "ok": bool(ok), "severity": severity, "detail": detail})

    login = auth_enabled()
    key_set = bool(os.getenv("SCOUTIQ_API_KEY"))
    add("access_control", "Access control", login or key_set, "high",
        "Sign-in is required." if login else "An API key is required." if key_set else
        "Anyone who can reach the server can read and change data. Set SCOUTIQ_AUTH_MODE=on (and a secret), or at least SCOUTIQ_API_KEY.")
    if login:
        add("auth_secret", "Token signing secret", len(os.getenv("SCOUTIQ_AUTH_SECRET", "")) >= 32, "high", "At least 32 characters are required.")
        add("bootstrap_password", "Bootstrap admin password removed", not os.getenv("SCOUTIQ_BOOTSTRAP_ADMIN_PASSWORD"), "medium",
            "Remove SCOUTIQ_BOOTSTRAP_ADMIN_PASSWORD from the environment after the first sign-in.")
    origins = cors_origins()
    add("cors", "Cross-origin access", "*" not in origins, "high" if "*" in origins else "low",
        "Any website may call the API from a browser." if "*" in origins else f"Allowed origins: {', '.join(origins)}.")
    add("rate_limit", "Rate limiting", _env_int("SCOUTIQ_RATE_LIMIT_PER_MINUTE", 600) > 0, "medium", "Requests per minute per client are capped." if _env_int("SCOUTIQ_RATE_LIMIT_PER_MINUTE", 600) > 0 else "Disabled: a single client can overload the server.")
    add("body_limit", "Request size limit", _env_int("SCOUTIQ_MAX_BODY_BYTES", 1_000_000) > 0, "medium", "Oversized request bodies are refused.")
    add("api_docs", "Interactive API docs hidden", not docs_enabled(), "low", "Set SCOUTIQ_ENABLE_DOCS=false in production." if docs_enabled() else "Docs are not served.")
    add("hsts", "HTTPS enforcement header", _on("SCOUTIQ_HSTS"), "low", "Set SCOUTIQ_HSTS=on when the site is served over HTTPS." if not _on("SCOUTIQ_HSTS") else "Enabled.")
    add("database", "Production database", not DATABASE_URL.startswith("sqlite"), "medium", "SQLite is for development; use PostgreSQL for shared deployments." if DATABASE_URL.startswith("sqlite") else "PostgreSQL.")
    failing = [c for c in checks if not c["ok"]]
    return {"checks": checks, "summary": {"passed": len(checks) - len(failing), "total": len(checks),
                                         "high_failing": sum(c["severity"] == "high" for c in failing), "medium_failing": sum(c["severity"] == "medium" for c in failing)}}


def log_startup_warnings() -> None:
    for c in security_posture()["checks"]:
        if not c["ok"] and c["severity"] in {"high", "medium"}:
            logger.warning("security: %s -- %s", c["title"], c["detail"])
