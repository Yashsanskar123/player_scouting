"""Building blocks for the club-first Dashboard: watchlist movers and affordable targets.

These are screening aids. Targets come from the same performance score and value data as the rest
of the platform (see the Model validation page for how far to trust each) -- they are suggestions
for a scout to check, never recommendations to sign.
"""
from __future__ import annotations

import pandas as pd

MIN_MOVE = 2.0          # ignore performance changes smaller than this (noise level)
MAX_TARGET_AGE = 31
RELIABLE_TIERS = {"Moderate", "High"}


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else pd.Series(index=frame.index, dtype=float)


def watchlist_movers(player_ids: list[str], facts: pd.DataFrame, season: int, limit: int = 5) -> list[dict]:
    """Shortlisted players whose performance score moved most versus their previous season."""
    if not player_ids or facts.empty:
        return []
    rows = facts[facts["player_id"].isin(set(player_ids))].sort_values("season")
    out = []
    for pid, g in rows.groupby("player_id"):
        current = g[g["season"] == season]
        earlier = g[g["season"] < season]
        if current.empty or earlier.empty:
            continue
        now, before = current.iloc[-1], earlier.iloc[-1]
        a, b = pd.to_numeric(now.get("performance_score"), errors="coerce"), pd.to_numeric(before.get("performance_score"), errors="coerce")
        if pd.isna(a) or pd.isna(b) or abs(a - b) < MIN_MOVE:
            continue
        out.append({"player_id": pid, "short_name": now.get("short_name"), "club_name": now.get("club_name"),
                    "performance_now": round(float(a), 1), "performance_before": round(float(b), 1), "change": round(float(a - b), 1),
                    "direction": "up" if a > b else "down", "previous_season": int(before["season"])})
    out.sort(key=lambda r: -abs(r["change"]))
    return out[:limit]


def affordable_targets(season_df: pd.DataFrame, club_name: str, priorities: list[dict], budget_eur: float | None, per_need: int = 3) -> list[dict]:
    """For each recruitment priority, players at that position who would raise the bar and fit the budget."""
    if season_df.empty:
        return []
    own = season_df[season_df["club_name"] == club_name]
    results = []
    for need in priorities:
        position = (need.get("recruitment_filter") or {}).get("canonical_position")
        if not position:
            continue
        own_level = _num(own[own["canonical_position"] == position], "performance_score")
        bar = max(float(own_level.max()) if own_level.notna().any() else 0.0, 55.0)
        pool = season_df[(season_df["canonical_position"] == position) & (season_df["club_name"] != club_name)]
        keep = (_num(pool, "performance_score") >= bar) & (_num(pool, "age_fifa") <= MAX_TARGET_AGE)
        if "sample_reliability_tier" in pool.columns:
            keep &= pool["sample_reliability_tier"].isin(RELIABLE_TIERS)
        if budget_eur is not None:
            keep &= _num(pool, "value_eur") <= budget_eur
        pool = pool[keep].copy()
        pool["_rank"] = _num(pool, "adjusted_performance_score").fillna(_num(pool, "performance_score"))
        candidates = []
        for _, r in pool.sort_values("_rank", ascending=False).head(per_need).iterrows():
            candidates.append({k: (None if pd.isna(r.get(k)) else r.get(k)) for k in
                               ("player_id", "short_name", "club_name", "league_name", "age_fifa", "performance_score", "adjusted_performance_score",
                                "value_eur", "value_gap_pct", "recruitment_risk_tier", "sample_reliability_tier")})
        results.append({"position": position, "need": need.get("need"), "severity": need.get("severity"),
                        "bar": round(bar, 1), "candidates": candidates,
                        "basis": f"{position}s rated at least {round(bar)} (your best, or 55), age {MAX_TARGET_AGE} or under, reliable sample"
                                 + (", within your transfer budget" if budget_eur is not None else "")})
    return results
