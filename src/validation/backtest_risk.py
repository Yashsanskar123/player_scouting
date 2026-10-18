"""Does the risk model's LOW/MEDIUM/HIGH tier actually predict anything
about what happens to a player next season?

Method: for every player-season transition we observe (player_id present
in season t and t+1), compute the actual change in performance_score and
in minutes played from t to t+1. Group these observed transitions by the
recruitment_risk_tier assigned AT season t (i.e. using only information
available at the time), and compare outcome distributions across tiers.

If HIGH-risk-tier players don't show worse subsequent outcomes than
LOW-risk-tier players, the risk score isn't adding real predictive
signal beyond its component definitions looking reasonable on paper.
"""
from __future__ import annotations

import pandas as pd


def backtest_risk_tiers(df: pd.DataFrame) -> dict:
    required = {"player_id", "season", "performance_score", "playing_time_min", "recruitment_risk_tier"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df is missing required columns: {missing}")

    transitions = []
    for player_id, group in df.groupby("player_id"):
        g = group.sort_values("season")
        seasons = g["season"].tolist()
        for i in range(len(seasons) - 1):
            row_t = g.iloc[i]
            row_t1 = g.iloc[i + 1]
            perf_t = pd.to_numeric(row_t["performance_score"], errors="coerce")
            perf_t1 = pd.to_numeric(row_t1["performance_score"], errors="coerce")
            min_t = pd.to_numeric(row_t["playing_time_min"], errors="coerce")
            min_t1 = pd.to_numeric(row_t1["playing_time_min"], errors="coerce")
            tier = row_t["recruitment_risk_tier"]
            if pd.isna(perf_t) or pd.isna(perf_t1) or pd.isna(tier):
                continue
            transitions.append({
                "player_id": player_id,
                "risk_tier_at_t": tier,
                "performance_delta": perf_t1 - perf_t,
                "minutes_delta": (min_t1 - min_t) if pd.notna(min_t) and pd.notna(min_t1) else None,
            })

    if not transitions:
        return {"n": 0, "note": "No usable season-to-season transitions found."}

    result_df = pd.DataFrame(transitions)
    summary = result_df.groupby("risk_tier_at_t").agg(
        n=("performance_delta", "size"),
        mean_performance_delta=("performance_delta", "mean"),
        median_performance_delta=("performance_delta", "median"),
        pct_declined=("performance_delta", lambda s: float((s < 0).mean() * 100)),
        mean_minutes_delta=("minutes_delta", "mean"),
    ).round(2)

    order = [t for t in ["LOW", "MEDIUM", "HIGH"] if t in summary.index]
    summary = summary.reindex(order)

    return {
        "n_transitions": len(result_df),
        "summary_by_risk_tier": summary,
    }
