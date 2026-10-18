"""Data coverage, freshness and health for the platform's own data (FIFA + FBref + Transfermarkt).

Every threshold is a named constant below so the rules are visible, and nothing is hidden or dropped:
this module only measures and reports.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.season_context import season_label

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "cleaned" / "fifa_fbref_merged_processed_v2.csv"
EXTERNAL = ROOT / "data" / "external"
MAPPINGS = ROOT / "data" / "mappings"

PARTIAL_BELOW = 0.80          # a season with < 80% of the previous season's players is "partial"
LIMITED_ADVANCED_BELOW = 0.70  # < 70% of players with advanced (xG etc.) statistics
NULL_DRIFT_POINTS = 10.0       # null-rate change versus other seasons that raises an alert
MEAN_DRIFT_Z = 2.0             # season mean this many standard deviations from the other seasons...
MEAN_DRIFT_MIN_RELATIVE = 0.10  # ...AND at least this far (10%) from them in absolute terms
STALE_AFTER_DAYS = 180

ADVANCED_COLUMN = "per_90_minutes_x_g"
KEY_COLUMNS = {
    "performance_score": "Performance score", "overall": "FIFA overall", "value_eur": "Market value", "wage_eur": "Wage",
    "fair_value_eur": "Fair value", ADVANCED_COLUMN: "Advanced stats (xG)", "playing_time_min": "Minutes played", "height_cm": "Height",
}
DRIFT_MEANS = {"performance_score": "Average performance score", "age_fifa": "Average age", "value_eur": "Median market value"}


def _pct(x: float) -> float:
    return round(float(x) * 100, 1)


def season_coverage(df: pd.DataFrame) -> dict[int, dict]:
    """Per season: size, breadth and whether it is a full season.

    A season is "partial" when leagues that normally appear are missing (a league is expected if it is
    present in at least half of all seasons), or when it has under PARTIAL_BELOW of the previous season's players.
    """
    if df.empty or "season" not in df.columns:
        return {}
    seasons = sorted(df["season"].unique())
    players = df.groupby("season")["player_id"].nunique()
    adv = df[ADVANCED_COLUMN].notna().groupby(df["season"]).mean() if ADVANCED_COLUMN in df.columns else pd.Series(1.0, index=players.index)
    leagues_by_season = df.groupby("season")["league_name"].agg(lambda x: set(x.dropna())) if "league_name" in df.columns else None
    expected: set = set()
    if leagues_by_season is not None and len(seasons) >= 2:
        counts = pd.Series([l for s in leagues_by_season for l in s]).value_counts()
        expected = set(counts[counts >= len(seasons) / 2].index)
    out = {}
    for i, s in enumerate(seasons):
        n, share = int(players[s]), float(adv.get(s, 1.0))
        present = leagues_by_season[s] if leagues_by_season is not None else set()
        missing = sorted(expected - present)
        prev = int(players[seasons[i - 1]]) if i > 0 else None
        vs_prev = n / prev if prev else None
        partial = bool(missing) or (vs_prev is not None and vs_prev < PARTIAL_BELOW)
        limited = share < LIMITED_ADVANCED_BELOW
        notes = []
        if missing:
            notes.append(f"Missing {len(missing)} of {len(expected)} usual leagues: {', '.join(missing)}.")
        if vs_prev is not None and vs_prev < PARTIAL_BELOW:
            notes.append(f"{n:,} players, {_pct(vs_prev)}% of the previous season ({prev:,}).")
        if partial:
            notes.append("Counts, averages and rankings are not comparable with full seasons.")
        if limited:
            notes.append(f"Advanced statistics exist for only {_pct(share)}% of players.")
        sub = df[df["season"] == s]
        out[int(s)] = {
            "rows": int(len(sub)), "players": n, "clubs": int(sub["club_name"].nunique()) if "club_name" in sub.columns else None,
            "leagues": len(present), "expected_leagues": len(expected), "missing_leagues": missing,
            "players_vs_previous_pct": _pct(vs_prev) if vs_prev is not None else None, "advanced_stats_pct": _pct(share),
            "status": "partial" if partial else "complete", "advanced_limited": bool(limited), "note": " ".join(notes),
        }
    return out


def missingness(df: pd.DataFrame) -> dict:
    cols = [c for c in KEY_COLUMNS if c in df.columns]
    table = []
    for s, g in df.groupby("season"):
        table.append({"season": int(s), "label": season_label(int(s)), **{c: _pct(g[c].isna().mean()) for c in cols}})
    return {"columns": [{"key": c, "label": KEY_COLUMNS[c]} for c in cols], "by_season": table}


def drift_alerts(df: pd.DataFrame) -> list[dict]:
    """Seasons whose data looks different from the rest: higher missingness or a shifted average."""
    alerts: list[dict] = []
    seasons = sorted(df["season"].unique())
    if len(seasons) < 4:
        return alerts
    for col, label in KEY_COLUMNS.items():
        if col not in df.columns:
            continue
        rates = df[col].isna().groupby(df["season"]).mean() * 100
        for s in seasons:
            typical = float(rates.drop(s).median())
            if rates[s] - typical >= NULL_DRIFT_POINTS:
                alerts.append({"kind": "missing_data", "season": int(s), "label": season_label(int(s)), "metric": label, "observed": round(float(rates[s]), 1),
                               "typical": round(typical, 1), "message": f"{label} is missing for {rates[s]:.0f}% of players in {season_label(int(s))} (typically {typical:.0f}%)."})
    for col, label in DRIFT_MEANS.items():
        if col not in df.columns:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        per = (vals.groupby(df["season"]).median() if col == "value_eur" else vals.groupby(df["season"]).mean()).dropna()
        for s in per.index:
            others = per.drop(s)
            sd = float(others.std())
            typical_mean = float(others.mean())
            if sd > 0 and abs(per[s] - typical_mean) / sd >= MEAN_DRIFT_Z and typical_mean and abs(per[s] / typical_mean - 1) >= MEAN_DRIFT_MIN_RELATIVE:
                alerts.append({"kind": "shifted_average", "season": int(s), "label": season_label(int(s)), "metric": label, "observed": round(float(per[s]), 2),
                               "typical": round(float(others.mean()), 2),
                               "message": f"{label} in {season_label(int(s))} is {per[s]:,.1f} against {others.mean():,.1f} in other seasons."})
    return sorted(alerts, key=lambda a: (a["season"], a["metric"]))


def _numeric(df: pd.DataFrame, col: str) -> pd.Series:
    """A numeric column, or an all-missing one when the data does not have it (checks then count zero rows)."""
    return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(np.nan, index=df.index)


def anomalies(df: pd.DataFrame) -> list[dict]:
    """Counts of rows worth a second look. Nothing is removed or changed."""
    out = []

    def add(key, title, mask, why):
        n = int(mask.sum())
        out.append({"key": key, "title": title, "rows": n, "share_pct": _pct(n / len(df)) if len(df) else 0.0, "why": why})

    age = _numeric(df, "age_fifa")
    add("score_floor", "Performance score of 0 after league adjustment", _numeric(df, "adjusted_performance_score").eq(0), "Very low scorers are floored at 0; these rows carry little information.")
    add("score_ceiling", "Performance score at 100", _numeric(df, "performance_score").ge(100), "Capped scores cannot be ranked against each other.")
    add("extreme_value_gap", "Fair value more than 3x market value", _numeric(df, "value_gap_pct").gt(200), "Usually low-minute players; the model is least reliable here.")
    add("age_outlier", "Age under 16 or over 40", age.lt(16) | age.gt(40), "Check the source rating or birth date.")
    add("tiny_samples", "Under 300 minutes played", _numeric(df, "playing_time_min").lt(300), "Statistics from very small samples are noisy; the reliability tier flags these.")
    return out


def identity_quality(df: pd.DataFrame) -> dict:
    conf = df["identity_confidence"].value_counts(normalize=True).mul(100).round(1).to_dict() if "identity_confidence" in df.columns else {}
    aliases = skipped = None
    try:
        aliases = int(len(pd.read_csv(MAPPINGS / "player_id_aliases.csv")))
        skipped = int(len(pd.read_csv(MAPPINGS / "player_id_alias_skipped.csv")))
    except Exception:
        pass
    link_rate = None
    try:
        link = pd.read_csv(EXTERNAL / "tm_player_link.csv", usecols=["player_id"], dtype=str)
        ids = set(df["player_id"].astype(str))
        link_rate = _pct(len(ids & set(link["player_id"])) / len(ids)) if ids else None
    except Exception:
        pass
    note = None
    if conf and max(conf.values()) >= 99:
        note = "Every row has the same identity-confidence level, so this field cannot tell a strong match from a weak one."
    return {"players": int(df["player_id"].nunique()), "identity_confidence_pct": conf, "identity_confidence_note": note, "merged_duplicate_ids": aliases,
            "duplicate_groups_left_for_review": skipped, "transfermarkt_link_rate_pct": link_rate}


@lru_cache(maxsize=4)
def _file_facts(path_str: str, mtime: float) -> dict:
    p = Path(path_str)
    out = {"modified": datetime.fromtimestamp(mtime, tz=timezone.utc).date().isoformat()}
    if p.name == "tm_valuations.csv":
        try:
            out["latest_record"] = pd.read_csv(p, usecols=["date"])["date"].max()
        except Exception:
            pass
    return out


def freshness(df: pd.DataFrame, today: date | None = None) -> list[dict]:
    """When each source was last updated, and whether that is stale. Dates come from the data files themselves."""
    today = today or date.today()
    latest = int(df["season"].max()) if not df.empty else None
    sources = []

    def add(name, covers, updated, note="", stale_override=None):
        age = (today - date.fromisoformat(updated)).days if updated else None
        stale = stale_override if stale_override is not None else (age is not None and age > STALE_AFTER_DAYS)
        sources.append({"source": name, "covers": covers, "updated": updated, "age_days": age, "stale": bool(stale), "note": note})

    if PROCESSED.exists():
        facts = _file_facts(str(PROCESSED), PROCESSED.stat().st_mtime)
        add("FIFA ratings + FBref statistics", f"Seasons through {season_label(latest)}" if latest else "—", facts["modified"],
            "FBref stopped publishing advanced statistics in January 2026, so this part of the data cannot be refreshed from that source.", stale_override=False)
    val = EXTERNAL / "tm_valuations.csv"
    if val.exists():
        facts = _file_facts(str(val), val.stat().st_mtime)
        newest = facts.get("latest_record") or facts["modified"]
        add("Transfermarkt (contracts, values, transfers)", f"Valuations up to {newest}", newest, "Current snapshot; used for contracts and market-value context.")
    return sources


def build_data_health(df: pd.DataFrame, quality: dict | None = None) -> dict:
    cov = season_coverage(df)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": int(len(df)), "players": int(df["player_id"].nunique()) if len(df) else 0,
        "quality_score": quality, "freshness": freshness(df),
        "coverage": [{"season": s, "label": season_label(s), **v} for s, v in cov.items()],
        "missingness": missingness(df), "drift_alerts": drift_alerts(df), "anomalies": anomalies(df), "identity": identity_quality(df),
    }
