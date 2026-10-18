"""Password hashing and signed tokens using only the standard library.

* Passwords: scrypt with a random per-user salt (constant-time verify).
* Tokens: base64url(payload).base64url(HMAC-SHA256) with an expiry. The role is
  NOT in the token: it is read from the database on every request, so role
  changes and deactivation take effect immediately.
Configuration (environment):
  SCOUTIQ_AUTH_MODE=on|off          default off (no login; current behaviour)
  SCOUTIQ_AUTH_SECRET=<32+ chars>   required when mode is on
  SCOUTIQ_TOKEN_TTL_MINUTES=480     token lifetime
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
MIN_PASSWORD_LENGTH = 10


class AuthConfigError(RuntimeError):
    pass


def auth_enabled() -> bool:
    return os.getenv("SCOUTIQ_AUTH_MODE", "off").strip().lower() in {"on", "true", "1", "enabled"}


def _secret() -> bytes:
    secret = os.getenv("SCOUTIQ_AUTH_SECRET", "")
    if len(secret) < 32:
        raise AuthConfigError("SCOUTIQ_AUTH_SECRET must be set to at least 32 characters when SCOUTIQ_AUTH_MODE=on.")
    return secret.encode()


def validate_auth_config() -> None:
    """Fail fast at startup instead of on the first login."""
    if auth_enabled():
        _secret()


def token_ttl_seconds() -> int:
    try:
        return max(60, int(os.getenv("SCOUTIQ_TOKEN_TTL_MINUTES", "480")) * 60)
    except ValueError:
        return 480 * 60


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=_b64d(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(digest, _b64d(expected))
    except Exception:
        return False


def create_token(username: str, now: float | None = None) -> str:
    issued = int(now if now is not None else time.time())
    payload = _b64e(json.dumps({"sub": username, "iat": issued, "exp": issued + token_ttl_seconds()}, separators=(",", ":")).encode())
    signature = _b64e(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def verify_token(token: str, now: float | None = None) -> dict | None:
    try:
        payload_b64, signature = token.split(".")
        expected = _b64e(hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64d(payload_b64))
        if payload["exp"] < (now if now is not None else time.time()):
            return None
        return payload
    except Exception:
        return None
