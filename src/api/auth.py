"""Minimal API key authentication (spec section 56's floor, not its
ceiling -- this is NOT role-based access control. RBAC (Admin/Sporting
Director/Analyst/Scout/Viewer, per the spec's role list) is real work
that needs actual user identity and a permissions model; it is not
attempted here.

What this DOES do: gate every route behind a single shared API key, read
from the SCOUTIQ_API_KEY environment variable, checked via the
`X-API-Key` request header. This is the floor above "every endpoint is
wide open to the internet," which is what existed before.

Deliberately opt-in: if SCOUTIQ_API_KEY is unset, auth is disabled
entirely and every request passes through unchecked -- so local
development and the existing test suite (which calls the API directly via
TestClient with no key) keep working with zero configuration. Set
SCOUTIQ_API_KEY before deploying anywhere reachable outside localhost.
"""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def get_configured_api_key() -> str | None:
    return os.getenv("SCOUTIQ_API_KEY")


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    configured_key = get_configured_api_key()
    if configured_key is None:
        return  # auth disabled -- no key configured
    if x_api_key is None or not hmac.compare_digest(x_api_key.encode(), configured_key.encode()):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")
