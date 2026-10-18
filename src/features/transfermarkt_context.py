"""Read-only Transfermarkt context for a ScoutIQ player.

Reads the sidecar files written by src/data/transfermarkt_link.py. If they are
missing (or the player is unmatched) every function degrades to
{"available": False} so callers and the UI never fail because of this layer.
The data is a point-in-time Transfermarkt snapshot (current contract/value),
NOT a per-season history of the ScoutIQ analysis season.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

EXTERNAL_DIR = Path(__file__).resolve().parents[2] / "data" / "external"
SNAPSHOT_NOTE = (
    "Transfermarkt snapshot (current contract, market value and transfer history). "
    "It is independent of the selected analysis season."
)


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NaT:
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value


@lru_cache(maxsize=1)
def _load() -> dict | None:
    link_path = EXTERNAL_DIR / "tm_player_link.csv"
    if not link_path.exists():
        return None
    link = pd.read_csv(link_path, dtype={"player_id": str})
    val_path = EXTERNAL_DIR / "tm_valuations.csv"
    tr_path = EXTERNAL_DIR / "tm_transfers.csv"
    val = pd.read_csv(val_path) if val_path.exists() else pd.DataFrame(columns=["tm_player_id", "date", "market_value_in_eur"])
    tr = pd.read_csv(tr_path) if tr_path.exists() else pd.DataFrame()
    val["date"] = pd.to_datetime(val["date"], errors="coerce")
    return {
        "link": link.set_index("player_id"),
        "val": {k: g.sort_values("date") for k, g in val.groupby("tm_player_id")},
        "tr": {k: g for k, g in tr.groupby("tm_player_id")} if len(tr) else {},
    }


def reload_cache() -> None:
    _load.cache_clear()
    _bulk_records.cache_clear()


def _contract_block(expiry: str | None, today: date) -> dict:
    if not expiry:
        return {"expires": None, "months_remaining": None, "status": "Unknown"}
    try:
        d = date.fromisoformat(str(expiry)[:10])
    except ValueError:
        return {"expires": None, "months_remaining": None, "status": "Unknown"}
    months = round((d - today).days / 30.4375, 1)
    if months < 0:
        status = "Expired / not renewed in snapshot"
    elif months <= 6:
        status = "Expiring within 6 months"
    elif months <= 12:
        status = "Expiring within 12 months"
    elif months <= 24:
        status = "1-2 years left"
    else:
        status = "2+ years left"
    return {"expires": d.isoformat(), "months_remaining": months, "status": status}


def get_context(player_id: str, as_of: date | None = None) -> dict:
    today = as_of or date.today()
    data = _load()
    if data is None or player_id not in data["link"].index:
        return {"available": False, "snapshot_note": SNAPSHOT_NOTE}
    row = data["link"].loc[player_id]
    tm_id = int(row["tm_player_id"])

    hist = data["val"].get(tm_id)
    history, change_12m, last_date = [], None, None
    if hist is not None and len(hist):
        hist = hist.dropna(subset=["date", "market_value_in_eur"])
        history = [{"date": d.strftime("%Y-%m-%d"), "value_eur": float(v)} for d, v in zip(hist["date"], hist["market_value_in_eur"])]
        if len(history) > 60:
            step = len(history) / 60
            history = [history[int(i * step)] for i in range(60)] + [history[-1]]
        if len(hist):
            latest = hist.iloc[-1]
            last_date = latest["date"].strftime("%Y-%m-%d")
            target = latest["date"] - pd.Timedelta(days=365)
            earlier = hist[hist["date"] <= target + pd.Timedelta(days=60)]
            if len(earlier):
                prev = earlier.iloc[-1]
                if abs((prev["date"] - target).days) <= 120 and prev["market_value_in_eur"] > 0:
                    change_12m = round((latest["market_value_in_eur"] / prev["market_value_in_eur"] - 1) * 100, 1)

    current = _clean(row.get("tm_market_value_eur"))
    peak = _clean(row.get("tm_peak_value_eur"))
    pct_peak = round(current / peak * 100, 1) if current and peak else None

    transfers = []
    tr = data["tr"].get(tm_id)
    if tr is not None:
        tr = tr.copy()
        tr["transfer_date"] = pd.to_datetime(tr["transfer_date"], errors="coerce")
        tr = tr[tr["transfer_date"].notna() & (tr["transfer_date"].dt.date <= today)].sort_values("transfer_date", ascending=False)
        for r in tr.head(8).itertuples(index=False):
            transfers.append({
                "date": r.transfer_date.strftime("%Y-%m-%d"),
                "season": _clean(r.transfer_season),
                "from_club": _clean(r.from_club_name),
                "to_club": _clean(r.to_club_name),
                "fee_eur": _clean(r.transfer_fee),
                "market_value_eur": _clean(r.market_value_in_eur),
            })

    return {
        "available": True,
        "snapshot_note": SNAPSHOT_NOTE,
        "match": {
            "confidence": _clean(row.get("match_confidence")),
            "shared_with_other_scoutiq_id": bool(_clean(row.get("tm_id_shared")) or False),
            "tm_name": _clean(row.get("tm_name")),
            "tm_url": _clean(row.get("tm_url")),
        },
        "profile": {
            "date_of_birth": _clean(row.get("date_of_birth")),
            "citizenship": _clean(row.get("country_of_citizenship")),
            "position": _clean(row.get("position")),
            "sub_position": _clean(row.get("sub_position")),
            "foot": _clean(row.get("foot")),
            "height_cm": _clean(row.get("height_in_cm")),
            "agent": _clean(row.get("agent_name")),
            "current_club": _clean(row.get("current_club_name")),
        },
        "contract": _contract_block(_clean(row.get("contract_expiration_date")), today),
        "market": {
            "current_value_eur": current,
            "peak_value_eur": peak,
            "pct_of_peak": pct_peak,
            "change_12m_pct": change_12m,
            "last_valuation_date": last_date,
        },
        "valuation_history": history,
        "transfers": transfers,
    }


def _contract_status_for(months):
    if months is None:
        return "Unknown"
    if months < 0:
        return "Expired / not renewed in snapshot"
    if months <= 6:
        return "Expiring within 6 months"
    if months <= 12:
        return "Expiring within 12 months"
    if months <= 24:
        return "1-2 years left"
    return "2+ years left"


@lru_cache(maxsize=1)
def _bulk_records() -> dict | None:
    """Per ScoutIQ player raw fields + 12-month value change, computed once (vectorised)."""
    data = _load()
    if data is None:
        return None
    link = data["link"].reset_index()
    val = pd.concat(list(data["val"].values()), ignore_index=True) if data["val"] else pd.DataFrame(columns=["tm_player_id", "date", "market_value_in_eur"])
    val = val.dropna(subset=["date", "market_value_in_eur"]).sort_values(["tm_player_id", "date"])
    change = pd.DataFrame(columns=["tm_player_id", "change_12m_pct"])
    if len(val):
        latest = val.groupby("tm_player_id").tail(1)[["tm_player_id", "date", "market_value_in_eur"]].rename(
            columns={"date": "latest_date", "market_value_in_eur": "latest_value"})
        latest["target"] = latest["latest_date"] - pd.Timedelta(days=365)
        latest["probe"] = latest["target"] + pd.Timedelta(days=60)
        prev = pd.merge_asof(
            latest.sort_values("probe"),
            val.rename(columns={"date": "prev_date", "market_value_in_eur": "prev_value"})[["tm_player_id", "prev_date", "prev_value"]].sort_values("prev_date"),
            left_on="probe", right_on="prev_date", by="tm_player_id", direction="backward")
        ok = prev["prev_date"].notna() & ((prev["prev_date"] - prev["target"]).abs() <= pd.Timedelta(days=120)) & (prev["prev_value"] > 0)
        prev["change_12m_pct"] = ((prev["latest_value"] / prev["prev_value"] - 1) * 100).round(1).where(ok)
        change = prev[["tm_player_id", "change_12m_pct"]]
    merged = link.merge(change, on="tm_player_id", how="left")
    return {pid: rec for pid, rec in zip(merged["player_id"], merged.to_dict("records"))}


def reload_bulk_cache() -> None:
    _bulk_records.cache_clear()


def bulk_contract_info(player_ids, as_of: date | None = None) -> dict:
    """{player_id: {...}} for the ids that have Transfermarkt data. Missing ids are simply absent."""
    records = _bulk_records()
    if records is None:
        return {}
    today = as_of or date.today()
    out = {}
    for pid in set(player_ids):
        r = records.get(pid)
        if r is None:
            continue
        block = _contract_block(_clean(r.get("contract_expiration_date")), today)
        current, peak = _clean(r.get("tm_market_value_eur")), _clean(r.get("tm_peak_value_eur"))
        out[pid] = {
            "contract_expires": block["expires"],
            "contract_months_left": block["months_remaining"],
            "contract_status": block["status"],
            "tm_value_eur": current,
            "tm_pct_of_peak": round(current / peak * 100, 1) if current and peak else None,
            "tm_value_change_12m_pct": _clean(r.get("change_12m_pct")),
            "tm_current_club": _clean(r.get("current_club_name")),
            "tm_link_confidence": _clean(r.get("match_confidence")),
        }
    return out


def contract_outlook(player_rows: list[dict], as_of: date | None = None) -> dict:
    """Summarise contract timing for a roster. player_rows need player_id (+ optional name/position/performance_score)."""
    info = bulk_contract_info([r["player_id"] for r in player_rows], as_of)
    buckets = {"expired_or_unrenewed": 0, "within_6m": 0, "within_12m": 0, "within_24m": 0, "longer": 0, "unknown": 0}
    expiring = []
    for r in player_rows:
        i = info.get(r["player_id"])
        months = i["contract_months_left"] if i else None
        if months is None:
            buckets["unknown"] += 1
            continue
        if months < 0:
            buckets["expired_or_unrenewed"] += 1
        elif months <= 6:
            buckets["within_6m"] += 1
        elif months <= 12:
            buckets["within_12m"] += 1
        elif months <= 24:
            buckets["within_24m"] += 1
        else:
            buckets["longer"] += 1
        if 0 <= months <= 12:
            expiring.append({**{k: r.get(k) for k in ("player_id", "short_name", "canonical_position", "performance_score", "age_fifa")}, **i})
    expiring.sort(key=lambda x: (x["contract_months_left"], -(x.get("performance_score") or 0)))
    covered = len(player_rows) - buckets["unknown"]
    return {
        "available": True,
        "coverage": {"with_contract_data": covered, "roster_size": len(player_rows)},
        "buckets": buckets,
        "expiring_within_12m": expiring[:15],
        "note": SNAPSHOT_NOTE + " Contracts may belong to a different club than the selected season's roster club.",
    }
