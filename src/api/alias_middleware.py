"""Rewrite merged (alias) player ids in request paths to their canonical id.

Applies only to /api/players/<id>... and /api/recruitment/players/<id>/...
so bookmarks, localStorage ids and old links keep working after a merge.
An id is rewritten ONLY when it no longer exists in the loaded data: before the
merge has been applied (`python -m src.identity.aliases apply`) alias ids still
exist and must be left alone, or players would 404 in seasons the canonical id lacks.
"""
from __future__ import annotations

from src.identity.aliases import load_aliases

_PREFIXES = ("/api/players/", "/api/recruitment/players/")
_known: dict = {"key": None, "ids": frozenset()}


def known_player_ids() -> frozenset:
    """Player ids present in the loaded data (cached until the data store is reloaded)."""
    try:
        from src.services.data_store import store
        facts = store.facts
        key = (id(facts), len(facts))
        if _known["key"] != key:
            ids = frozenset(facts["player_id"].astype(str)) if "player_id" in facts.columns else frozenset()
            _known.update(key=key, ids=ids)
        return _known["ids"]
    except Exception:
        return frozenset()


def canonical_player_id(player_id: str) -> str:
    """Map a merged (old) player id to its surviving id, but only when the old id is gone from the loaded data.

    Used for ids sent in request bodies (the middleware above handles ids in URLs), so stale ids held by an
    open browser tab or an old link keep working after `python -m src.identity.aliases apply`.
    """
    aliases = load_aliases()
    if player_id in aliases and player_id not in known_player_ids():
        return aliases[player_id]
    return player_id


class AliasPathMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            aliases = load_aliases()
            path = scope.get("path", "")
            if aliases:
                for prefix in _PREFIXES:
                    if path.startswith(prefix):
                        rest = path[len(prefix):]
                        head, sep, tail = rest.partition("/")
                        if head in aliases and head not in known_player_ids():
                            new_path = f"{prefix}{aliases[head]}{sep}{tail}"
                            scope = dict(scope, path=new_path, raw_path=new_path.encode())
                        break
        await self.app(scope, receive, send)
