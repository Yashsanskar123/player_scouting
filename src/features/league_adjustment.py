"""League-strength adjustment (spec section 29) -- previously entirely
unimplemented. Percentiles and scores were computed within (position,
season) peer groups but never corrected for the fact that a CDM's stats
in the Eredivisie and a CDM's stats in the Premier League are not
directly comparable.

METHOD (data-driven, per spec section 29's own suggested approach: "use
cross-league transfers, post-transfer performance, historical performance
translation" -- not a hand-picked coefficient table):

This dataset has 2,474 real player-seasons where the same player_id
changed league_name between consecutive seasons. For each transition,
performance_score_after - performance_score_before is one noisy
observation of the relative strength gap between the two leagues. Pooling
all transitions, this becomes a paired-comparison problem (the same
structure as Bradley-Terry ratings or Elo): solve, via least squares, for
one latent "strength" value per league such that the fitted gaps best
explain the observed deltas, anchored by fixing one league (the one with
the most total player-seasons) at 0.

Sign convention: a HIGHER strength value means players' raw performance
scores tend to be HIGHER in that league relative to the anchor -- i.e.
stats are easier to produce there. `adjusted_performance_score` SUBTRACTS
a league's strength, so a player in a stat-inflating league is discounted
and a player in a tougher league is credited.

REAL, UNRESOLVED LIMITATION -- stated plainly, not hidden: league
transfers are not random. Players who move to a "bigger" league are
disproportionately the ones already improving or being rewarded for good
form, and players moving to a "smaller" league are disproportionately
those in decline or seeking playing time. This selection effect is
CONFOUNDED with genuine league-difficulty differences in the same
direction the model would attribute to league strength, and this method
cannot separate the two. Treat the output as a first-pass, directional
signal, not a precise difficulty ranking -- and see
docs/VALIDATION.md for what a sanity check against the result actually
showed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_league_transitions(df: pd.DataFrame) -> pd.DataFrame:
    """Every consecutive-season league change for the same player_id,
    with the resulting performance_score delta.
    """
    required = {"player_id", "season", "league_name", "performance_score"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df is missing required columns: {missing}")

    rows = []
    for player_id, group in df.groupby("player_id"):
        g = group.sort_values("season")[["season", "league_name", "performance_score"]].dropna()
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            if a["league_name"] != b["league_name"]:
                rows.append({
                    "player_id": player_id,
                    "from_league": a["league_name"],
                    "to_league": b["league_name"],
                    "performance_delta": b["performance_score"] - a["performance_score"],
                })
    return pd.DataFrame(rows)


def fit_league_strength(df: pd.DataFrame, min_transitions: int = 10) -> dict:
    """Returns {league_name: strength} via least-squares over the paired
    transitions, plus fit diagnostics. Leagues with fewer than
    min_transitions total appearances in the transition data are dropped
    from the fit (too little evidence to estimate reliably) and reported
    separately as 'insufficient_data_leagues'.
    """
    transitions = build_league_transitions(df)
    if transitions.empty:
        return {"strengths": {}, "insufficient_data_leagues": [], "n_transitions": 0}

    league_counts = pd.concat([transitions["from_league"], transitions["to_league"]]).value_counts()
    valid_leagues = set(league_counts[league_counts >= min_transitions].index)
    insufficient = sorted(set(league_counts.index) - valid_leagues)

    fit_data = transitions[
        transitions["from_league"].isin(valid_leagues) & transitions["to_league"].isin(valid_leagues)
    ]
    if fit_data.empty:
        return {"strengths": {}, "insufficient_data_leagues": insufficient, "n_transitions": 0}

    leagues = sorted(valid_leagues)
    league_idx = {lg: i for i, lg in enumerate(leagues)}
    anchor = league_counts.loc[leagues].idxmax()  # most-observed league = reference point, strength fixed at 0

    n = len(fit_data)
    k = len(leagues)
    X = np.zeros((n, k))
    y = fit_data["performance_delta"].to_numpy()
    for row_i, (_, row) in enumerate(fit_data.iterrows()):
        X[row_i, league_idx[row["to_league"]]] += 1
        X[row_i, league_idx[row["from_league"]]] -= 1

    anchor_col = league_idx[anchor]
    X_reduced = np.delete(X, anchor_col, axis=1)
    coeffs, residuals, rank, _ = np.linalg.lstsq(X_reduced, y, rcond=None)

    strengths = {}
    j = 0
    for lg in leagues:
        if lg == anchor:
            strengths[lg] = 0.0
        else:
            strengths[lg] = round(float(coeffs[j]), 2)
            j += 1

    ss_res = float(np.sum((y - X_reduced @ coeffs) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return {
        "strengths": strengths,
        "anchor_league": anchor,
        "insufficient_data_leagues": insufficient,
        "n_transitions": int(n),
        "n_leagues_fit": k,
        "r_squared": round(r_squared, 3),
    }


def apply_league_adjustment(df: pd.DataFrame, strengths: dict) -> pd.DataFrame:
    df = df.copy()
    league_strength = df["league_name"].map(strengths).fillna(0)
    df["league_strength_adjustment"] = league_strength.round(2)
    df["adjusted_performance_score"] = (
        pd.to_numeric(df["performance_score"], errors="coerce") - league_strength
    ).clip(0, 100).round(1)
    return df
