"""Club profiles (club, formation, budgets) stored in data/club_profile.json.

Several clubs can be saved; exactly one is *active* and supplies the defaults for the
Dashboard, Squad Audit and Optimizer. A small JSON file keeps this free of database
migrations. The older single-club file format is read as-is and upgraded on the next save.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parents[2] / "data" / "club_profile.json"
FALLBACK_FORMATIONS = ["4-3-3", "4-4-2", "4-2-3-1", "3-5-2", "3-4-3", "5-3-2"]


def valid_formations() -> list[str]:
    try:
        from src.optimization.squad_optimizer import FORMATIONS
        return list(FORMATIONS)
    except Exception:
        return FALLBACK_FORMATIONS


def _read() -> dict:
    """Always returns {"active": name|None, "clubs": {name: profile}} (upgrading the old format in memory)."""
    try:
        raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"active": None, "clubs": {}}
    if isinstance(raw, dict) and "club_name" in raw:  # legacy single-club file
        return {"active": raw["club_name"], "clubs": {raw["club_name"]: raw}}
    clubs = raw.get("clubs") if isinstance(raw, dict) else None
    if not isinstance(clubs, dict):
        return {"active": None, "clubs": {}}
    active = raw.get("active") if raw.get("active") in clubs else (next(iter(clubs)) if clubs else None)
    return {"active": active, "clubs": clubs}


def _write(state: dict) -> None:
    if not state["clubs"]:
        clear_profile()
        return
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps({"version": 2, **state}, indent=2), encoding="utf-8")


def load_profile() -> dict | None:
    """The ACTIVE club's profile (what the rest of the app uses), or None."""
    state = _read()
    return state["clubs"].get(state["active"]) if state["active"] else None


def list_profiles() -> dict:
    state = _read()
    return {"active": state["active"], "clubs": list(state["clubs"].values())}


def _money(value, label: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.")
    if number < 0 or number != number:
        raise ValueError(f"{label} must be zero or more.")
    return number


def save_profile(club_name: str, formation: str, transfer_budget_eur=None, wage_budget_eur=None, valid_clubs=None) -> dict:
    """Create or update a club and make it the active one."""
    club_name = (club_name or "").strip()
    if not club_name:
        raise ValueError("club_name is required.")
    if valid_clubs is not None and club_name not in valid_clubs:
        raise ValueError(f"Unknown club '{club_name}'.")
    if formation not in valid_formations():
        raise ValueError(f"Unknown formation '{formation}'. Available: {valid_formations()}")
    profile = {
        "club_name": club_name,
        "formation": formation,
        "transfer_budget_eur": _money(transfer_budget_eur, "transfer_budget_eur"),
        "wage_budget_eur": _money(wage_budget_eur, "wage_budget_eur"),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    state = _read()
    state["clubs"][club_name] = profile
    state["active"] = club_name
    _write(state)
    return profile


def set_active(club_name: str) -> dict:
    state = _read()
    if club_name not in state["clubs"]:
        raise ValueError(f"'{club_name}' is not a saved club.")
    state["active"] = club_name
    _write(state)
    return state["clubs"][club_name]


def delete_profile(club_name: str | None = None) -> None:
    """Remove one saved club (default: the active one). If it was active, another saved club takes over."""
    state = _read()
    target = club_name or state["active"]
    if target not in state["clubs"]:
        return
    del state["clubs"][target]
    if state["active"] == target:
        state["active"] = next(iter(state["clubs"]), None)
    _write(state)


def clear_profile() -> None:
    try:
        PROFILE_PATH.unlink()
    except FileNotFoundError:
        pass
