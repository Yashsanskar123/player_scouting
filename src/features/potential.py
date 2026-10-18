"""Potential & trajectory model (spec sections 12-13).

REVISION NOTE: the first version of this module fit a linear trend on
each player's performance_score history and extrapolated it forward. A
walk-forward backtest against this dataset's own multi-season history
(src/validation/backtest_potential.py) showed that approach was WORSE
than doing nothing: MAE 13.88 vs. 9.89 for a naive "assume no change from
last season" baseline, correlation with actual next-season performance
0.39 vs 0.51. Per-player histories here are short (3-8 seasons) and noisy
enough that a fitted slope overreacts and extrapolates noise, not signal.

The blend implemented below -- 0.4 * last_observed_value + 0.6 *
historical_mean -- was found by grid search against the same backtest and
beat every tested alternative (raw trend, shrunk trend, EWMA at several
decay rates, mean-only): MAE 9.13, the best result found. This is a
regression-to-the-mean estimator, not a "detects breakout talent" model --
that limitation is real and stated in docs/MODEL_CARD.md's companion
note, not hidden.

Current ability and potential remain separate, clearly-labeled outputs.
FIFA's `potential` rating is used only as one input/benchmark for players
without enough history to blend, never as ground truth (spec 67) -- it's
exposed unchanged as `fifa_potential_benchmark`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Blend weight on the most recent observed value vs. the player's own
# historical mean, for `expected_performance_12m`. Found by grid search
# (see src/validation/backtest_potential.py) over {0.0, 0.1, ..., 1.0};
# 0.4 had the lowest backtested MAE (9.13) among all weights and
# alternative estimators (raw trend, EWMA) tested.
RECENCY_WEIGHT = 0.4
MIN_SEASONS_FOR_BLEND = 2  # with 2 seasons, mean == the earlier value, so this degrades gracefully


def _age_prior(age: float) -> float:
    """Age-based prior for how much developmental room a player likely
    has left, used only for players with no usable season history to
    blend from at all."""
    if pd.isna(age):
        return 0.4
    if age <= 19:
        return 1.0
    if age <= 23:
        return 0.75
    if age <= 27:
        return 0.35
    if age <= 31:
        return 0.10
    return 0.0


def compute_potential(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fifa_potential_benchmark"] = pd.to_numeric(df.get("potential"), errors="coerce")
    df["current_ability"] = pd.to_numeric(df.get("performance_score"), errors="coerce")

    df["trend_source"] = "age_curve_prior"
    df["expected_performance_12m"] = pd.NA
    df["development_potential"] = pd.NA

    if "player_id" not in df.columns or "season" not in df.columns:
        return df

    history_counts = df.groupby("player_id")["season"].transform("nunique")
    has_history = history_counts >= MIN_SEASONS_FOR_BLEND

    # --- Players with real season history: validated recency/mean blend ---
    # (this blend is what the backtest validated -- it predicts
    # `expected_performance_12m` only. `development_potential` below uses
    # the same age-curve + FIFA-potential-gap formula for every player,
    # history or not, since that formula has NOT itself been backtested
    # and inventing a second, different "upside" formula just for
    # multi-season players would be introducing an unvalidated signal
    # under the cover of a validated one.)
    for player_id, group in df[has_history].groupby("player_id"):
        g = group.sort_values("season")
        y = pd.to_numeric(g["performance_score"], errors="coerce").to_numpy()
        valid_mask = ~np.isnan(y)
        if valid_mask.sum() < MIN_SEASONS_FOR_BLEND:
            continue
        valid_y = y[valid_mask]
        last_value = valid_y[-1]
        history_mean = valid_y.mean()
        blended = RECENCY_WEIGHT * last_value + (1 - RECENCY_WEIGHT) * history_mean

        last_idx = g.index[-1]
        df.loc[g.index, "trend_source"] = "recency_mean_blend"
        df.loc[last_idx, "expected_performance_12m"] = round(float(np.clip(blended, 0, 100)), 1)

    # --- development_potential: same formula for every player (age room +
    # FIFA-rated ceiling gap), independent of season history. Not yet
    # backtested -- see docs/MODEL_CARD.md. ---
    ages = pd.to_numeric(df.get("age_fifa"), errors="coerce")
    age_room = ages.map(_age_prior)
    fifa_gap = (df["fifa_potential_benchmark"] - df["current_ability"]).clip(lower=0)
    development_potential = df["current_ability"] + (age_room * 15) * 0.5 + fifa_gap.fillna(0) * 0.5
    df["development_potential"] = development_potential.clip(0, 100).round(1)

    # --- Players without usable history: age-curve fallback for the
    # point prediction too, since there's no season data to blend from. ---
    fallback_mask = df["expected_performance_12m"].isna()
    df.loc[fallback_mask, "expected_performance_12m"] = (
        df.loc[fallback_mask, "current_ability"] + age_room.loc[fallback_mask] * 3
    ).clip(0, 100).round(1)

    return df
