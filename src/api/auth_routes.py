"""Login, current user, user administration and audit-log endpoints."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth import service
from src.auth.permissions import ROLE_PERMISSIONS, ROLES
from src.auth.security import auth_enabled, create_token, token_ttl_seconds, verify_password
from src.db.models import AuditLog
from src.db.session import get_session

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "analyst"
    display_name: str | None = None


class UserUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None
    display_name: str | None = None


def _me_payload(user) -> dict:
    return {**service.user_public(user), "permissions": sorted(ROLE_PERMISSIONS.get(user.role, set()))}


@router.get("/api/auth/status")
def auth_status() -> dict:
    return {"auth_enabled": auth_enabled(), "roles": ROLES}


@router.post("/api/auth/login")
def login(req: LoginRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    if not auth_enabled():
        raise HTTPException(status_code=400, detail="Authentication is not enabled on this server.")
    service.ensure_bootstrap_admin(session)
    username = service.normalize_username(req.username)
    ip = request.client.host if request.client else None
    request_id = getattr(request.state, "request_id", None)

    def audit(action: str, status: int, role: str | None = None) -> None:
        service.record_audit(session, username=username or "unknown", role=role, action=action, method="POST",
                             path="/api/auth/login", status=status, request_id=request_id, ip=ip)

    if service.is_locked(username):
        audit("auth.locked", 429)
        raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Try again in a few minutes.")
    user = service.get_user(session, username)
    # Same message and similar work for unknown user / wrong password / inactive user.
    ok = bool(user and user.is_active and verify_password(req.password, user.password_hash))
    if not ok:
        if user is None:
            verify_password(req.password, "scrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        service.register_failure(username)
        audit("auth.login_failed", 401)
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    service.clear_failures(username)
    user.last_login_at = dt.datetime.utcnow()
    session.commit()
    audit("auth.login", 200, user.role)
    return {"access_token": create_token(user.username), "token_type": "bearer", "expires_in": token_ttl_seconds(), "user": _me_payload(user)}


@router.get("/api/auth/me")
def me(request: Request, session: Session = Depends(get_session)) -> dict:
    info = getattr(request.state, "auth_user", None)
    if not auth_enabled() or not info:
        return {"auth_enabled": auth_enabled(), "authenticated": False, "user": None}
    user = service.get_user(session, info["username"])
    return {"auth_enabled": True, "authenticated": True, "user": _me_payload(user)}


@router.get("/api/users")
def list_users(session: Session = Depends(get_session)) -> dict:
    from src.db.models import User
    users = session.scalars(select(User).order_by(User.username)).all()
    return {"users": [service.user_public(u) for u in users], "roles": ROLES}


@router.post("/api/users", status_code=201)
def create_user(req: UserCreateRequest, session: Session = Depends(get_session)) -> dict:
    try:
        user = service.create_user(session, req.username, req.password, req.role, req.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.user_public(user)


@router.patch("/api/users/{username}")
def update_user(username: str, req: UserUpdateRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    user = service.get_user(session, username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    new_role = req.role if req.role is not None else user.role
    new_active = req.is_active if req.is_active is not None else bool(user.is_active)
    if new_role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ROLES}.")
    losing_admin = user.role == "admin" and user.is_active and (new_role != "admin" or not new_active)
    if losing_admin and service.count_active_admins(session) <= 1:
        raise HTTPException(status_code=400, detail="At least one active admin must remain.")
    if req.password is not None:
        try:
            service.validate_password(req.password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        from src.auth.security import hash_password
        user.password_hash = hash_password(req.password)
        service.clear_failures(user.username)
    user.role, user.is_active = new_role, 1 if new_active else 0
    if req.display_name is not None:
        user.display_name = req.display_name[:128]
    session.commit()
    return service.user_public(user)


@router.get("/api/audit-log")
def audit_log(limit: int = 100, offset: int = 0, username: str | None = None, action: str | None = None,
              session: Session = Depends(get_session)) -> dict:
    limit = max(1, min(limit, 500))
    query = select(AuditLog)
    count = select(func.count()).select_from(AuditLog)
    if username:
        query, count = query.where(AuditLog.username == username), count.where(AuditLog.username == username)
    if action:
        query, count = query.where(AuditLog.action == action), count.where(AuditLog.action == action)
    rows = session.scalars(query.order_by(AuditLog.id.desc()).offset(max(0, offset)).limit(limit)).all()
    return {
        "total": session.scalar(count) or 0,
        "items": [{"id": r.id, "ts": r.ts.isoformat() if r.ts else None, "username": r.username, "role": r.role,
                   "action": r.action, "method": r.method, "path": r.path, "status": r.status, "entity": r.entity,
                   "request_id": r.request_id, "ip": r.ip} for r in rows],
    }
