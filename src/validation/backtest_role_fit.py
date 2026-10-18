"""Construct validity check for role-fit archetypes.

The sanity checks used so far (Messi/Haaland top "Poacher") are a weak
validation standard -- they'd pass almost any reasonable formula, since
those players are elite on nearly every metric simultaneously. This is a
real test instead: does a player's role_fit_score for their position's
archetype predict something in the real world BEYOND what their raw
performance_score already explains?

Method: for players with a following season in the data, correlate
role_fit_score (season t) against playing_time_min (season t+1) --
minutes are a genuine real-world signal (a coach's revealed judgment
about whether a player's profile is worth deploying), not something we
computed. Critically, this reports the PARTIAL correlation controlling
for performance_score, not the raw correlation -- a raw correlation would
mostly just re-detect "better players play more," which role_fit doesn't
need to explain (performance_score already does). The question that
actually validates the archetype definitions is whether role_fit adds
INCREMENTAL signal once performance is already accounted for.
"""
from __future__ import annotations

import pandas as pd

from src.features.role_archetypes import compute_role_fit, recommended_roles_for_position


def _partial_correlation(x: pd.Series, y: pd.Series, z: pd.Series) -> float:
    """partial_corr(x, y | z) via the standard formula from pairwise
    Pearson correlations. Returns NaN if degenerate (e.g. z perfectly
    determines x or y)."""
    r_xy = x.corr(y)
    r_xz = x.corr(z)
    r_yz = y.corr(z)
    denom = ((1 - r_xz ** 2) * (1 - r_yz ** 2)) ** 0.5
    if denom == 0 or pd.isna(denom):
        return float("nan")
    return (r_xy - r_xz * r_yz) / denom


def validate_role_fit_against_future_minutes(df: pd.DataFrame, role: str) -> dict:
    position_group = None
    from src.features.role_archetypes import ROLE_ARCHETYPES
    cfg = ROLE_ARCHETYPES.get(role)
    if cfg is None:
        raise ValueError(f"Unknown role: {role}")

    scored = compute_role_fit(df, role)

    rows = []
    for player_id, group in scored.groupby("player_id"):
        g = group.sort_values("season")
        for i in range(len(g) - 1):
            cur, nxt = g.iloc[i], g.iloc[i + 1]
            if pd.isna(cur.get("role_fit_score")) or pd.isna(cur.get("performance_score")):
                continue
            if pd.isna(nxt.get("playing_time_min")):
                continue
            rows.append({
                "player_id": player_id,
                "role_fit_t": cur["role_fit_score"],
                "performance_t": cur["performance_score"],
                "minutes_t1": nxt["playing_time_min"],
            })

    if len(rows) < 30:
        return {"role": role, "n": len(rows), "note": "Too few player-seasons with a following season to test."}

    pair_df = pd.DataFrame(rows)
    raw_corr = pair_df["role_fit_t"].corr(pair_df["minutes_t1"])
    partial_corr = _partial_correlation(pair_df["role_fit_t"], pair_df["minutes_t1"], pair_df["performance_t"])
    performance_raw_corr = pair_df["performance_t"].corr(pair_df["minutes_t1"])

    return {
        "role": role,
        "n": len(pair_df),
        "raw_correlation_role_fit_vs_future_minutes": round(float(raw_corr), 3),
        "raw_correlation_performance_vs_future_minutes": round(float(performance_raw_corr), 3),
        "partial_correlation_role_fit_vs_future_minutes_controlling_for_performance": round(float(partial_corr), 3),
    }
