"""Role -> permission matrix and the request classifier.

Permissions: read, write_scouting (shortlists/notes), write_club (club profile), admin.
Roles:       analyst (read) < scout (+write_scouting) < director (+write_club) < admin (all).
Unknown non-GET endpoints require admin (deny by default).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ROLE_PERMISSIONS = {
    "analyst": {"read"},
    "scout": {"read", "write_scouting"},
    "director": {"read", "write_scouting", "write_club"},
    "admin": {"read", "write_scouting", "write_club", "admin"},
}
ROLES = list(ROLE_PERMISSIONS)

# POST endpoints that only compute/read (no state change): allowed with "read".
READ_ONLY_POSTS = {
    "/api/players/compare", "/api/replacement/search", "/api/scouting/search",
    "/api/squads/audit", "/api/transfers/simulate", "/api/squads/optimize",
}
PUBLIC = {
    ("GET", "/health"), ("GET", "/ready"), ("GET", "/docs"), ("GET", "/redoc"), ("GET", "/openapi.json"),
    ("GET", "/api/auth/status"), ("POST", "/api/auth/login"),
}


@dataclass(frozen=True)
class Rule:
    permission: str          # public | authenticated | read | write_scouting | write_club | admin
    action: str | None = None  # audit action for state-changing requests
    entity: str | None = None


_RULES: list[tuple[str, re.Pattern, str, str | None]] = [
    ("GET", re.compile(r"^/api/auth/me$"), "authenticated", None),
    ("GET", re.compile(r"^/api/audit-log$"), "admin", None),
    ("GET", re.compile(r"^/api/admin/security-status$"), "admin", None),
    ("GET", re.compile(r"^/api/users$"), "admin", None),
    ("POST", re.compile(r"^/api/users$"), "admin", "user.create"),
    ("PATCH", re.compile(r"^/api/users/(?P<entity>[^/]+)$"), "admin", "user.update"),
    # Exports are read-only but recorded in the audit trail (data leaving the platform).
    ("GET", re.compile(r"^/api/players/(?P<entity>[^/]+)/report\.pdf$"), "read", "export.player_report"),
    ("GET", re.compile(r"^/api/contracts/board/export\.pdf$"), "read", "export.contract_board"),
    ("GET", re.compile(r"^/api/recruitment/shortlists/(?P<entity>[^/]+)/export\.pdf$"), "read", "export.shortlist_pdf"),
    ("GET", re.compile(r"^/api/recruitment/shortlists/(?P<entity>[^/]+)/export\.xlsx$"), "read", "export.shortlist"),
    ("GET", re.compile(r"^/api/market/opportunities/export\.xlsx$"), "read", "export.opportunities"),
    ("GET", re.compile(r"^/api/club-profile/report\.pdf$"), "read", "export.club_report"),
    ("POST", re.compile(r"^/api/admin/reload$"), "admin", "admin.reload"),
    ("PUT", re.compile(r"^/api/club-profile$"), "write_club", "club_profile.update"),
    ("DELETE", re.compile(r"^/api/club-profile$"), "write_club", "club_profile.reset"),
    ("POST", re.compile(r"^/api/club-profile/activate$"), "write_club", "club_profile.activate"),
    ("POST", re.compile(r"^/api/recruitment/shortlists$"), "write_scouting", "shortlist.create"),
    ("POST", re.compile(r"^/api/recruitment/shortlists/(?P<entity>[^/]+)/entries$"), "write_scouting", "shortlist.add_entry"),
    ("PATCH", re.compile(r"^/api/recruitment/entries/(?P<entity>[^/]+)$"), "write_scouting", "shortlist.update_entry"),
    ("POST", re.compile(r"^/api/recruitment/players/(?P<entity>[^/]+)/notes$"), "write_scouting", "note.create"),
]


def classify(method: str, path: str) -> Rule:
    method = method.upper()
    path = path.rstrip("/") or "/"
    if (method, path) in PUBLIC:
        return Rule("public")
    for rule_method, pattern, permission, action in _RULES:
        match = pattern.match(path)
        if rule_method == method and match:
            return Rule(permission, action, match.groupdict().get("entity"))
    if method in {"GET", "HEAD", "OPTIONS"}:
        return Rule("read")
    if method == "POST" and path in READ_ONLY_POSTS:
        return Rule("read")
    return Rule("admin", "unknown.mutation")


def role_allows(role: str, permission: str) -> bool:
    if permission in {"public", "authenticated"}:
        return True
    return permission in ROLE_PERMISSIONS.get(role, set())
