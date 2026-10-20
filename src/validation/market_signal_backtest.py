"""Chronological screening of alternative market-discovery signals.

Signals use only historical FIFA/FBref player-season facts. Performance and
market-value percentiles are computed within the same season and canonical
position; age-adjusted performance ranks within three-year age bands. No
current Transfermarkt contract snapshot is joined into historical seasons.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "player_id",
    "season",
    "performance_score",
    "playing_time_min",
    "value_eur",
    "age_fifa",
}


def _rank_pct(series: pd.Series) -> pd.Series:
    return series.rank(pct=True, method="average") * 100


def _correlation(left: pd.Series, right: pd.Series) -> float | None:
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None
    value = left.corr(right, method="spearman")
    return round(float(value), 4) if pd.notna(value) else None


def evaluate_market_signals(
    facts: pd.DataFrame,
    min_minutes: int = 450,
) -> dict:
    """Compare three season-t signals against the player's season-(t+1) outcomes.

    Value efficiency is performance percentile minus log-market-value
    percentile. Age-adjusted performance is the performance percentile within
    the player's position, season, and three-year age band.
    """
    missing = sorted(REQUIRED_COLUMNS - set(facts.columns))
    if missing:
        return {
            "available": False,
            "reason": f"Missing required columns: {', '.join(missing)}",
            "n_pairs": 0,
            "results": [],
        }
    if min_minutes < 0:
        raise ValueError("min_minutes must be non-negative.")

    columns = list(REQUIRED_COLUMNS)
    if "canonical_position" in facts.columns:
        columns.append("canonical_position")
    data = facts[columns].copy()
    for column in ("season", "performance_score", "playing_time_min", "value_eur", "age_fifa"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=list(REQUIRED_COLUMNS))
    data = (
        data.sort_values("playing_time_min", ascending=False)
        .drop_duplicates(["player_id", "season"])
    )
    position_season = ["season", "canonical_position"] if "canonical_position" in data.columns else ["season"]
    data["_performance_percentile"] = data.groupby(position_season)["performance_score"].transform(_rank_pct)
    log_value = np.log1p(data["value_eur"].clip(lower=0))
    data["_value_percentile"] = log_value.groupby(
        [data[column] for column in position_season]
    ).transform(_rank_pct)
    data["performance_baseline"] = data["_performance_percentile"]
    data["performance_value_efficiency"] = data["_performance_percentile"] - data["_value_percentile"]
    data["_age_band"] = (data["age_fifa"] // 3).astype(int)
    data["age_adjusted_performance"] = data.groupby(
        position_season + ["_age_band"]
    )["performance_score"].transform(_rank_pct)

    seasons = sorted(data["season"].unique().tolist())
    next_season = {seasons[index]: seasons[index + 1] for index in range(len(seasons) - 1)}
    data["_next_season"] = data["season"].map(next_season)
    following = data[["player_id", "season", "performance_score", "playing_time_min"]].rename(columns={
        "season": "_next_season",
        "performance_score": "next_performance",
        "playing_time_min": "next_minutes",
    })
    pairs = data.merge(following, on=["player_id", "_next_season"], how="inner", validate="one_to_one")
    pairs = pairs[pairs["playing_time_min"] >= min_minutes].copy()

    if pairs.empty:
        return {
            "available": False,
            "reason": "No adjacent-season player pairs met the minimum-minute requirement.",
            "min_minutes_previous_season": min_minutes,
            "n_pairs": 0,
            "results": [],
        }

    results = []
    for signal in (
        "performance_baseline",
        "performance_value_efficiency",
        "age_adjusted_performance",
    ):
        values = pairs[signal]
        top_decile = values >= values.quantile(0.9)
        results.append({
            "signal": signal,
            "n_pairs": int(len(pairs)),
            "spearman_next_minutes": _correlation(values, pairs["next_minutes"]),
            "spearman_next_performance": _correlation(values, pairs["next_performance"]),
            "top_decile_next_minutes_median": round(float(pairs.loc[top_decile, "next_minutes"].median()), 1),
            "cohort_next_minutes_median": round(float(pairs["next_minutes"].median()), 1),
        })

    baseline = next(result for result in results if result["signal"] == "performance_baseline")
    for result in results:
        baseline_corr = baseline["spearman_next_minutes"]
        current_corr = result["spearman_next_minutes"]
        result["minutes_lift_vs_baseline"] = (
            round(current_corr - baseline_corr, 4)
            if current_corr is not None and baseline_corr is not None
            else None
        )

    return {
        "available": True,
        "method": (
            "Adjacent-season chronological pairing; same-season position "
            "percentile; no current contract snapshot used historically."
        ),
        "min_minutes_previous_season": min_minutes,
        "n_pairs": int(len(pairs)),
        "n_seasons": int(pairs["season"].nunique()),
        "results": results,
        "promotion_rule": (
            "Do not promote a candidate from this pooled screen alone. Require "
            "positive improvement over baseline on next-season minutes and "
            "performance, then replicate by held-out season."
        ),
    }