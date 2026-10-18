"""Dashboard-level recruitment intelligence.

The dashboard should aggregate at the player-season level rather than treating
raw source rows as independent players. Trend metrics require a minimum sample
of minutes in both seasons to reduce small-sample noise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


TREND_MIN_MINUTES = 900
IMPROVEMENT_THRESHOLD = 8.0
BREAKOUT_MIN_AGE = 23
BREAKOUT_MIN_PERFORMANCE = 60.0
BREAKOUT_MIN_POTENTIAL = 75.0
BREAKOUT_MIN_DELTA = 5.0


def _num(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def canonical_player_season(df: pd.DataFrame) -> pd.DataFrame:
    """Return one deterministic row per player-season.

    When source joins create duplicate player-season rows, prefer the row with
    the greatest playing-time sample, then the highest performance score.
    This avoids counting source duplicates as separate players.
    """
    if df.empty or "player_id" not in df.columns:
        return df.copy()

    work = df.copy()
    work["_minutes"] = _num(work, "playing_time_min").fillna(-1)
    work["_performance"] = _num(work, "performance_score").fillna(-np.inf)
    work = work.sort_values(
        ["player_id", "_minutes", "_performance"],
        ascending=[True, False, False],
        kind="mergesort",
    )
    work = work.drop_duplicates(subset=["player_id"], keep="first")
    return work.drop(columns=["_minutes", "_performance"], errors="ignore")


def season_snapshot(facts: pd.DataFrame, season: int) -> dict:
    df = canonical_player_season(facts[facts["season"] == season])
    if df.empty:
        return {
            "season": season,
            "player_count": 0,
            "average_performance": None,
            "median_value_eur": None,
            "average_potential": None,
            "median_minutes": None,
        }

    return {
        "season": season,
        "player_count": int(df["player_id"].nunique()),
        "average_performance": _num(df, "performance_score").mean(),
        "median_value_eur": _num(df, "value_eur").median(),
        "average_potential": _num(df, "development_potential").mean(),
        "median_minutes": _num(df, "playing_time_min").median(),
    }


def season_movers(facts: pd.DataFrame, season: int, limit: int = 5) -> dict:
    seasons = sorted(pd.to_numeric(facts["season"], errors="coerce").dropna().astype(int).unique())
    previous = max((s for s in seasons if s < season), default=None)
    if previous is None:
        return {
            "season": season,
            "previous_season": None,
            "eligible_players": 0,
            "improved_total": 0,
            "declined_total": 0,
            "improved": [],
            "declined": [],
            "method": {"min_minutes_each_season": TREND_MIN_MINUTES},
        }

    current = canonical_player_season(facts[facts["season"] == season]).copy()
    prior = canonical_player_season(facts[facts["season"] == previous]).copy()

    columns = [
        "player_id", "short_name", "canonical_position", "club_name",
        "age_fifa", "performance_score", "playing_time_min",
        "development_potential", "value_eur",
    ]
    columns = [c for c in columns if c in current.columns]
    current = current[columns].copy()
    prior = prior[[c for c in columns if c in prior.columns]].copy()

    rename_current = {c: f"current_{c}" for c in columns if c != "player_id"}
    rename_prior = {c: f"previous_{c}" for c in columns if c != "player_id"}
    current = current.rename(columns=rename_current)
    prior = prior.rename(columns=rename_prior)

    merged = current.merge(prior, on="player_id", how="inner")
    merged["current_minutes"] = _num(merged, "current_playing_time_min")
    merged["previous_minutes"] = _num(merged, "previous_playing_time_min")
    merged["current_performance"] = _num(merged, "current_performance_score")
    merged["previous_performance"] = _num(merged, "previous_performance_score")
    merged["performance_delta"] = merged["current_performance"] - merged["previous_performance"]

    eligible = merged[
        (merged["current_minutes"] >= TREND_MIN_MINUTES)
        & (merged["previous_minutes"] >= TREND_MIN_MINUTES)
        & merged["current_performance"].notna()
        & merged["previous_performance"].notna()
    ].copy()

    def format_rows(frame: pd.DataFrame) -> list[dict]:
        rows = []
        for _, row in frame.head(limit).iterrows():
            rows.append({
                "player_id": str(row["player_id"]),
                "short_name": row.get("current_short_name"),
                "canonical_position": row.get("current_canonical_position"),
                "club_name": row.get("current_club_name"),
                "age_fifa": row.get("current_age_fifa"),
                "current_performance": row.get("current_performance"),
                "previous_performance": row.get("previous_performance"),
                "performance_delta": row.get("performance_delta"),
                "current_minutes": row.get("current_minutes"),
                "development_potential": row.get("current_development_potential"),
                "value_eur": row.get("current_value_eur"),
            })
        return rows

    improved = eligible[eligible["performance_delta"] >= IMPROVEMENT_THRESHOLD].sort_values(
        "performance_delta", ascending=False
    )
    declined = eligible[eligible["performance_delta"] <= -IMPROVEMENT_THRESHOLD].sort_values(
        "performance_delta", ascending=True
    )

    return {
        "season": season,
        "previous_season": previous,
        "eligible_players": int(len(eligible)),
        "improved_total": int(len(improved)),
        "declined_total": int(len(declined)),
        "improved": format_rows(improved),
        "declined": format_rows(declined),
        "method": {
            "min_minutes_each_season": TREND_MIN_MINUTES,
            "performance_change_threshold": IMPROVEMENT_THRESHOLD,
        },
    }


def breakout_candidates(facts: pd.DataFrame, season: int, limit: int = 6) -> dict:
    seasons = sorted(pd.to_numeric(facts["season"], errors="coerce").dropna().astype(int).unique())
    previous = max((s for s in seasons if s < season), default=None)
    if previous is None:
        return {"season": season, "previous_season": None, "total": 0, "results": [], "method": {}}

    current = canonical_player_season(facts[facts["season"] == season]).copy()
    prior = canonical_player_season(facts[facts["season"] == previous]).copy()

    cols = ["player_id", "short_name", "canonical_position", "club_name", "age_fifa",
            "performance_score", "playing_time_min", "development_potential", "value_eur"]
    current = current[[c for c in cols if c in current.columns]].rename(
        columns={c: f"current_{c}" for c in cols if c != "player_id"}
    )
    prior = prior[[c for c in cols if c in prior.columns]].rename(
        columns={c: f"previous_{c}" for c in cols if c != "player_id"}
    )
    merged = current.merge(prior, on="player_id", how="inner")
    merged["current_performance"] = _num(merged, "current_performance_score")
    merged["previous_performance"] = _num(merged, "previous_performance_score")
    merged["delta"] = merged["current_performance"] - merged["previous_performance"]
    merged["current_minutes"] = _num(merged, "current_playing_time_min")
    merged["previous_minutes"] = _num(merged, "previous_playing_time_min")
    merged["age"] = _num(merged, "current_age_fifa")
    merged["potential"] = _num(merged, "current_development_potential")

    candidates = merged[
        (merged["age"] <= BREAKOUT_MIN_AGE)
        & (merged["current_minutes"] >= TREND_MIN_MINUTES)
        & (merged["previous_minutes"] >= TREND_MIN_MINUTES)
        & (merged["current_performance"] >= BREAKOUT_MIN_PERFORMANCE)
        & (merged["potential"] >= BREAKOUT_MIN_POTENTIAL)
        & (merged["delta"] >= BREAKOUT_MIN_DELTA)
    ].copy()

    # Transparent composite: improvement is the strongest signal, potential is
    # the second signal, and current performance is a floor rather than a rank.
    candidates["breakout_score"] = (
        candidates["delta"].clip(lower=0) * 0.6
        + candidates["potential"].clip(lower=0) * 0.25
        + candidates["current_performance"].clip(lower=0) * 0.15
    )
    candidates = candidates.sort_values("breakout_score", ascending=False)

    results = []
    for _, row in candidates.head(limit).iterrows():
        results.append({
            "player_id": str(row["player_id"]),
            "short_name": row.get("current_short_name"),
            "canonical_position": row.get("current_canonical_position"),
            "club_name": row.get("current_club_name"),
            "age_fifa": row.get("age"),
            "current_performance": row.get("current_performance"),
            "performance_delta": row.get("delta"),
            "development_potential": row.get("potential"),
            "current_minutes": row.get("current_minutes"),
            "value_eur": row.get("current_value_eur"),
            "breakout_score": row.get("breakout_score"),
        })

    return {
        "season": season,
        "previous_season": previous,
        "total": int(len(candidates)),
        "results": results,
        "method": {
            "max_age": BREAKOUT_MIN_AGE,
            "min_minutes_each_season": TREND_MIN_MINUTES,
            "min_current_performance": BREAKOUT_MIN_PERFORMANCE,
            "min_potential": BREAKOUT_MIN_POTENTIAL,
            "min_performance_delta": BREAKOUT_MIN_DELTA,
        },
    }


def dashboard_overview(facts: pd.DataFrame, season: int, market_total: int | None = None) -> dict:
    if facts.empty or "season" not in facts.columns:
        return {
            "season": season,
            "snapshot": season_snapshot(pd.DataFrame({"season": []}), season),
            "movers": season_movers(pd.DataFrame({"season": []}), season),
            "breakout": breakout_candidates(pd.DataFrame({"season": []}), season),
            "market_opportunities_total": market_total,
        }

    snapshot = season_snapshot(facts, season)
    movers = season_movers(facts, season)
    breakout = breakout_candidates(facts, season)
    return {
        "season": season,
        "snapshot": snapshot,
        "movers": movers,
        "breakout": breakout,
        "market_opportunities_total": market_total,
    }
