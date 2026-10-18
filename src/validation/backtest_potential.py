"""Backtest: does the trend-based potential model actually predict
anything, using data we already have?

Method (walk-forward, not the production `compute_potential` function,
which predicts one step BEYOND the available data and so can't be
backtested directly): for every player with >= 3 observed seasons, hide
their most recent season, fit a linear trend on the performance_score of
the seasons before it, and predict the hidden season. Compare against two
naive baselines on the same held-out point:
  - naive_last: assume no change from the last observed value
  - mean_history: assume regression to the player's own historical mean

If our trend model doesn't beat naive_last, the "trend" signal isn't
adding predictive value over just looking at last season's number, and
should be reported as such rather than presented as a real potential
prediction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def backtest_trend_model(df: pd.DataFrame, min_seasons: int = 3) -> dict:
    if "player_id" not in df.columns or "season" not in df.columns or "performance_score" not in df.columns:
        raise ValueError("df must have player_id, season, performance_score columns.")

    counts = df.groupby("player_id")["season"].transform("nunique")
    eligible = df[counts >= min_seasons]

    records = []
    for player_id, group in eligible.groupby("player_id"):
        g = group.sort_values("season")
        y = pd.to_numeric(g["performance_score"], errors="coerce").to_numpy()
        if np.isnan(y).any() or len(y) < min_seasons:
            continue

        train_y = y[:-1]
        actual_next = y[-1]

        x = np.arange(len(train_y))
        slope = np.polyfit(x, train_y, 1)[0]
        pred_trend = train_y[-1] + slope
        pred_naive_last = train_y[-1]
        pred_mean_history = train_y.mean()

        records.append({
            "player_id": player_id,
            "actual": actual_next,
            "pred_trend": pred_trend,
            "pred_naive_last": pred_naive_last,
            "pred_mean_history": pred_mean_history,
        })

    if not records:
        return {"n": 0, "note": "No players had enough season history to backtest."}

    result_df = pd.DataFrame(records)

    def _metrics(pred_col: str) -> dict:
        err = result_df["actual"] - result_df[pred_col]
        mae = err.abs().mean()
        corr = result_df["actual"].corr(result_df[pred_col])
        return {"MAE": round(float(mae), 2), "correlation_with_actual": round(float(corr), 3)}

    return {
        "n": len(result_df),
        "min_seasons_required": min_seasons,
        "trend_model": _metrics("pred_trend"),
        "naive_last_value_baseline": _metrics("pred_naive_last"),
        "mean_history_baseline": _metrics("pred_mean_history"),
        "detail": result_df,
    }
