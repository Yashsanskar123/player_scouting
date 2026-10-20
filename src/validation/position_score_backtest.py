"""Position-specific score stability and next-season minutes diagnostic."""
from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = {
    "player_id",
    "season",
    "canonical_position",
    "performance_score",
    "playing_time_min",
    "value_eur",
}


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    if left.nunique(dropna=True) < 2 or right.nunique(dropna=True) < 2:
        return None
    value = left.corr(right, method="spearman")
    return round(float(value), 4) if pd.notna(value) else None


def evaluate_position_scores(
    facts: pd.DataFrame,
    min_minutes: int = 450,
) -> dict:
    """Measure GK and CB score stability, next-season minutes, and market agreement.

    Pairs use adjacent observed seasons. The minutes threshold applies to the
    scored season; next-season minutes remain the outcome and are not filtered.
    Market-value correlations are computed within each position-season before
    being combined, avoiding a pooled cross-season price trend.
    """
    missing = sorted(REQUIRED_COLUMNS - set(facts.columns))
    if missing:
        return {
            "available": False,
            "reason": f"Missing required columns: {', '.join(missing)}",
            "positions": [],
        }
    if min_minutes < 0:
        raise ValueError("min_minutes must be non-negative.")

    data = facts[list(REQUIRED_COLUMNS)].copy()
    for column in ("season", "performance_score", "playing_time_min", "value_eur"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=list(REQUIRED_COLUMNS))
    data = (
        data.sort_values(["playing_time_min", "performance_score"], ascending=False)
        .drop_duplicates(["player_id", "season"])
    )
    seasons = sorted(data["season"].unique().tolist())
    next_season = {seasons[index]: seasons[index + 1] for index in range(len(seasons) - 1)}

    paired_frames = []
    for season, following_season in next_season.items():
        current = data[data["season"] == season].copy()
        following = data.loc[
            data["season"] == following_season,
            ["player_id", "performance_score", "playing_time_min"],
        ].rename(columns={
            "performance_score": "next_performance_score",
            "playing_time_min": "next_minutes",
        })
        pairs = current.merge(following, on="player_id", how="inner", validate="one_to_one")
        pairs = pairs[
            (pairs["playing_time_min"] >= min_minutes)
            & pairs["next_performance_score"].notna()
            & pairs["next_minutes"].notna()
        ].copy()
        if not pairs.empty:
            paired_frames.append(pairs)

    if not paired_frames:
        return {
            "available": True,
            "min_minutes_previous_season": min_minutes,
            "n_pairs": 0,
            "n_seasons": 0,
            "positions": [],
            "method": "Adjacent observed seasons; market value is diagnostic only, not the target.",
        }

    pairs = pd.concat(paired_frames, ignore_index=True)
    position_results = []
    for position in ("GK", "CB"):
        position_mask = pairs["canonical_position"].astype(str).str.upper().str.startswith(position)
        group = pairs[position_mask]
        same = data[data["canonical_position"].astype(str).str.upper().str.startswith(position)]
        if len(group) < 30:
            position_results.append({
                "position": position,
                "n_pairs": int(len(group)),
                "available": False,
                "reason": "Fewer than 30 adjacent-season player observations.",
            })
            continue
        performance = group["performance_score"]
        top_decile = performance >= performance.quantile(0.9)
        stability = _spearman(performance, group["next_performance_score"])
        position_results.append({
            "position": position,
            "n_pairs": int(len(group)),
            "available": True,
            "spearman_score_vs_next_minutes": _spearman(performance, group["next_minutes"]),
            "spearman_score_vs_next_performance": stability,
            "spearman_score_vs_market_value": _spearman(same["performance_score"], same["value_eur"]),
            "year_to_year_score_stability": stability,
            "n_seasons": int(group["season"].nunique()),
        })

    return {
        "available": True,
        "method": "Adjacent observed seasons; prior-season score predicts next-season minutes/performance; market-value correlation is diagnostic only, not the target.",
        "min_minutes_previous_season": min_minutes,
        "n_pairs": int(len(pairs)),
        "n_seasons": int(pairs["season"].nunique()),
        "positions": position_results,
    }