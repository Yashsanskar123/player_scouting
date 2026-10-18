"""FastAPI dependency enforcing authentication + role permissions.

With SCOUTIQ_AUTH_MODE off (default) it never blocks anything; it only tags
state-changing requests so the audit middleware can record them as 'anonymous'.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.auth import service
from src.auth.permissions import classify, role_allows
from src.auth.security import auth_enabled, verify_token
from src.db.session import get_session


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def authorize(request: Request, session: Session = Depends(get_session)) -> None:
    rule = classify(request.method, request.url.path)
    state = request.state
    state.audit_action = rule.action
    state.audit_entity = rule.entity
    state.auth_user = None

    if rule.permission == "public" or not auth_enabled():
        return

    def deny(status: int, detail: str, action: str) -> None:
        service.record_audit(session, username=getattr(state, "denied_user", None) or "unknown", role=None, action=action,
                             method=request.method, path=request.url.path, status=status,
                             request_id=getattr(state, "request_id", None), ip=_client_ip(request))
        state.audit_action = None  # already recorded
        raise HTTPException(status_code=status, detail=detail, headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)

    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    payload = verify_token(token) if token else None
    if not payload:
        deny(401, "Authentication required. Sign in again.", "auth.denied")
    user = service.get_user(session, payload["sub"])
    if user is None or not user.is_active:
        deny(401, "Account is not active.", "auth.denied")
    state.auth_user = {"username": user.username, "role": user.role}
    state.denied_user = user.username
    if not role_allows(user.role, rule.permission):
        deny(403, f"Your role ({user.role}) does not allow this action.", "auth.forbidden")
