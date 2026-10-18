from __future__ import annotations

from collections import OrderedDict

import numpy as np
import pandas as pd


def canonical_player_season(df: pd.DataFrame) -> pd.DataFrame:
    """Keep one source row per player-season for longitudinal calculations."""
    if df.empty or "player_id" not in df.columns or "season" not in df.columns:
        return df.copy()
    work = df.copy()
    work["season"] = pd.to_numeric(work["season"], errors="coerce").astype("Int64")
    work = work[work["season"].notna()].copy()
    work["season"] = work["season"].astype(int)
    work["_minutes"] = pd.to_numeric(work.get("playing_time_min"), errors="coerce").fillna(0)
    work["_performance"] = pd.to_numeric(work.get("performance_score"), errors="coerce")
    work = work.sort_values(["player_id", "season", "_minutes", "_performance"], ascending=[True, True, False, False])
    work = work.drop_duplicates(["player_id", "season"], keep="first")
    return work.drop(columns=["_minutes", "_performance"], errors="ignore")


def _slope(values: pd.Series) -> float | None:
    values = pd.to_numeric(values, errors="coerce").dropna()
    if len(values) < 2:
        return None
    x = np.arange(len(values), dtype=float)
    return float(np.polyfit(x, values.to_numpy(dtype=float), 1)[0])


FEATURE_COLUMNS = ["three_year_avg_performance", "five_year_avg_performance", "performance_consistency_std", "performance_trend_per_season",
                   "career_minutes_to_date", "seasons_played_to_date", "seasons_900m_to_date", "career_peak_performance"]


def player_longitudinal_features(facts: pd.DataFrame, season: int) -> pd.DataFrame:
    """Player-level historical evidence relative to a selected season.

    Vectorised: one grouped pass over the table instead of a Python loop per player. The values are identical
    to the original per-player implementation (kept as a reference in tests/test_search_intelligence.py).
    """
    df = canonical_player_season(facts)
    if df.empty:
        return pd.DataFrame(columns=["player_id"])

    seasons = sorted(pd.to_numeric(df["season"], errors="coerce").dropna().astype(int).unique())
    prior = [s for s in seasons if s <= season]
    if not prior:
        return pd.DataFrame(columns=["player_id"])

    last3, last5 = prior[-3:], prior[-5:]
    scoped = df[df["season"].isin(prior)].copy()
    scoped["_perf"] = pd.to_numeric(scoped.get("performance_score"), errors="coerce")
    scoped["_minutes"] = pd.to_numeric(scoped.get("playing_time_min"), errors="coerce").fillna(0)
    scoped = scoped.sort_values(["player_id", "season"], kind="mergesort")
    by = scoped.groupby("player_id", sort=False)

    out = pd.DataFrame({"player_id": scoped["player_id"].drop_duplicates().to_numpy()}).set_index("player_id")
    recent5 = scoped[scoped["season"].isin(last5)].dropna(subset=["_perf"]).groupby("player_id")["_perf"]
    out["three_year_avg_performance"] = scoped[scoped["season"].isin(last3)].dropna(subset=["_perf"]).groupby("player_id")["_perf"].mean()
    out["five_year_avg_performance"] = recent5.mean()
    std5 = recent5.std(ddof=0)
    out["performance_consistency_std"] = std5.where(recent5.size() >= 2)

    # Trend: least-squares slope of eligible (900+ minute) performance against 0..n-1, as np.polyfit(x, y, 1)[0] gave.
    eligible = scoped[(scoped["_minutes"] >= 900)].dropna(subset=["_perf"]).copy()
    eligible["_i"] = eligible.groupby("player_id").cumcount().astype(float)
    eligible["_iy"] = eligible["_i"] * eligible["_perf"]
    eligible["_ii"] = eligible["_i"] ** 2
    g = eligible.groupby("player_id")
    n, si, sy, siy, sii = g.size().astype(float), g["_i"].sum(), g["_perf"].sum(), g["_iy"].sum(), g["_ii"].sum()
    denom = n * sii - si ** 2
    out["performance_trend_per_season"] = ((n * siy - si * sy) / denom).where(n >= 2)

    out["career_minutes_to_date"] = by["_minutes"].sum().astype(float)
    out["seasons_played_to_date"] = by["season"].nunique().astype(int)
    out["seasons_900m_to_date"] = scoped.assign(_e=(scoped["_minutes"] >= 900).astype(int)).groupby("player_id")["_e"].sum().astype(int)
    out["career_peak_performance"] = by["_perf"].max()
    return out.reset_index()[["player_id"] + FEATURE_COLUMNS]


_FEATURE_CACHE: "OrderedDict[tuple, pd.DataFrame]" = OrderedDict()
_FEATURE_CACHE_SIZE = 12


def cached_longitudinal_features(facts: pd.DataFrame, season: int) -> pd.DataFrame:
    """The features depend only on the data and the selected season, so compute them once per data version."""
    key = (id(facts), len(facts), int(season))
    if key not in _FEATURE_CACHE:
        _FEATURE_CACHE[key] = player_longitudinal_features(facts, season)
        while len(_FEATURE_CACHE) > _FEATURE_CACHE_SIZE:
            _FEATURE_CACHE.popitem(last=False)
    _FEATURE_CACHE.move_to_end(key)
    return _FEATURE_CACHE[key]


def enrich_search_results(df: pd.DataFrame, facts: pd.DataFrame, season: int) -> pd.DataFrame:
    features = cached_longitudinal_features(facts, season)
    if features.empty:
        return df.copy()
    return df.merge(features, on="player_id", how="left")
