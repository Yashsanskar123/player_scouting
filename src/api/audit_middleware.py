"""Writes one audit row for each completed state-changing request.

Reads what the `authorize` dependency left in scope["state"]; failures are
swallowed (and logged) so auditing can never break a request. Request bodies
are never stored. Uses the app's get_session (including test overrides).
"""
from __future__ import annotations

import logging

from starlette.concurrency import run_in_threadpool

from src.auth import service
from src.db.session import get_session

logger = logging.getLogger("scoutiq.audit")


def _write(app, row: dict) -> None:
    factory = getattr(app, "dependency_overrides", {}).get(get_session, get_session)
    gen = factory()
    session = next(gen)
    try:
        service.record_audit(session, **row)
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


class AuditMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            state = scope.get("state") or {}
            action = state.get("audit_action")
            if action:
                user = state.get("auth_user") or {}
                client = scope.get("client")
                row = dict(
                    username=user.get("username") or "anonymous", role=user.get("role"), action=action,
                    method=scope.get("method"), path=scope.get("path"), status=status["code"],
                    entity=state.get("audit_entity"), request_id=state.get("request_id"),
                    ip=client[0] if client else None,
                )
                try:
                    await run_in_threadpool(_write, scope.get("app"), row)
                except Exception:
                    logger.error("audit middleware failed", exc_info=True)
