"""User management, login throttling and audit writing. All DB access takes a Session."""
from __future__ import annotations

import logging
import os
import re
import threading
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.permissions import ROLES
from src.auth.security import MIN_PASSWORD_LENGTH, hash_password
from src.db.models import AuditLog, User

logger = logging.getLogger("scoutiq.audit")
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,64}$")

# --- login throttle: 5 failures per username per 5 minutes (in-memory, per process)
MAX_FAILURES, WINDOW_SECONDS = 5, 300
_failures: dict[str, list[float]] = {}
_lock = threading.Lock()


def _recent(username: str, now: float) -> list[float]:
    return [t for t in _failures.get(username, []) if now - t < WINDOW_SECONDS]


def is_locked(username: str, now: float | None = None) -> bool:
    now = now if now is not None else time.time()
    with _lock:
        return len(_recent(username, now)) >= MAX_FAILURES


def register_failure(username: str, now: float | None = None) -> None:
    now = now if now is not None else time.time()
    with _lock:
        _failures[username] = _recent(username, now) + [now]


def clear_failures(username: str | None = None) -> None:
    with _lock:
        if username is None:
            _failures.clear()
        else:
            _failures.pop(username, None)


# --- users
def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def validate_new_user(username: str, password: str, role: str) -> None:
    if not USERNAME_RE.match(username):
        raise ValueError("Username must be 3-64 characters: lowercase letters, digits, '.', '_' or '-'.")
    validate_password(password)
    if role not in ROLES:
        raise ValueError(f"Role must be one of {ROLES}.")


def validate_password(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")


def get_user(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == normalize_username(username)))


def count_users(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(User)) or 0


def count_active_admins(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active == 1)) or 0


def create_user(session: Session, username: str, password: str, role: str, display_name: str | None = None) -> User:
    username = normalize_username(username)
    validate_new_user(username, password, role)
    if get_user(session, username):
        raise ValueError("That username already exists.")
    user = User(username=username, display_name=(display_name or username)[:128], password_hash=hash_password(password), role=role, is_active=1)
    session.add(user)
    session.commit()
    return user


def ensure_bootstrap_admin(session: Session) -> None:
    """If there are no users yet, create the first admin from environment variables (if set)."""
    if count_users(session) > 0:
        return
    username = normalize_username(os.getenv("SCOUTIQ_BOOTSTRAP_ADMIN_USER", ""))
    password = os.getenv("SCOUTIQ_BOOTSTRAP_ADMIN_PASSWORD", "")
    if username and password:
        try:
            create_user(session, username, password, "admin", "Administrator")
            logger.info("bootstrap admin created", extra={"fields": {"username": username}})
        except ValueError as exc:
            logger.error("bootstrap admin not created: %s", exc)


def user_public(user: User) -> dict:
    return {
        "username": user.username, "display_name": user.display_name, "role": user.role,
        "is_active": bool(user.is_active),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


# --- audit
def record_audit(session: Session, *, username: str, role: str | None, action: str, method: str | None = None,
                 path: str | None = None, status: int | None = None, entity: str | None = None,
                 request_id: str | None = None, ip: str | None = None) -> None:
    """Failure-safe: an audit problem must never break the request."""
    try:
        session.add(AuditLog(username=(username or "anonymous")[:64], role=role, action=action[:64], method=method,
                             path=(path or "")[:255], status=status, entity=(entity or None) and entity[:128],
                             request_id=request_id, ip=ip))
        session.commit()
    except Exception:
        session.rollback()
        logger.error("audit write failed", exc_info=True)


def ensure_auth_tables(engine=None) -> None:
    """Create only the users/audit_log tables if missing (existing databases predate them). Idempotent."""
    from src.db.models import Base
    if engine is None:
        from src.db.session import engine as default_engine
        engine = default_engine
    Base.metadata.create_all(engine, tables=[User.__table__, AuditLog.__table__], checkfirst=True)
