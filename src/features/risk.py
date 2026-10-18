"""Recruitment risk model (spec sections 30-31).

VALIDATED SCOPE (see src/validation/backtest_risk.py and
docs/VALIDATION.md for the full backtest): this score predicts outcome
UNCERTAINTY, not outcome DIRECTION. Backtesting against 17,851 real
season-to-season transitions in this dataset showed HIGH-tier players do
NOT show worse average next-season performance than LOW-tier players
(mean delta actually slightly positive for HIGH, -0.44 for LOW) -- but
HIGH-tier players do show much higher variance in outcome (std=22.9 vs.
12.6 for LOW, 17.2 for MEDIUM), a real and monotonic separation. This
makes sense structurally: age_risk flags both very young players (real
breakout upside) and ageing players (real decline downside) as "risky,"
which cancels out in the mean but shows up clearly in spread.

Practical implication for how this score should be used: a HIGH
recruitment_risk_tier means "this signing could go either significantly
better or significantly worse than projected" -- a volatility warning,
not a "will underperform" prediction. Do not read it as the latter.

We only model risk categories we can actually observe in this data.
Injury history is explicitly NOT fabricated (spec section 30/66): if that
data isn't available, it isn't scored, not estimated.
"""
from __future__ import annotations

import pandas as pd

TOP_LEAGUES = {"Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"}


def compute_risk(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- Age risk: very young (unproven ceiling) or ageing (decline risk) ---
    age = pd.to_numeric(df.get("age_fifa", pd.Series(dtype=float, index=df.index)), errors="coerce")
    age_risk = pd.Series(20.0, index=df.index)  # baseline
    age_risk = age_risk.where(age.isna(), 0)
    age_risk = age_risk + ((age < 20).astype(float) * 25) + ((age > 31).astype(float) * 35) + \
        (((age >= 20) & (age <= 29)).astype(float) * 5)
    df["age_risk"] = age_risk.clip(0, 100).round(1)

    # --- Data reliability risk: from sample_reliability_score (inverse).
    # Falls back to an empty (all-NaN) Series -- not None -- if the
    # column is absent, so `.fillna()` below always has a Series to call,
    # not a bare scalar. This function is meant to be called after
    # compute_reliability_score in the pipeline, but shouldn't crash on a
    # differently-ordered or partial input; it should just be less
    # informative (defaults to a neutral 50 reliability assumption). ---
    reliability = pd.to_numeric(
        df.get("sample_reliability_score", pd.Series(dtype=float, index=df.index)), errors="coerce"
    )
    df["availability_risk"] = (100 - reliability.fillna(50)).round(1)

    # --- Adaptation / league transition risk: proxy via current league tier ---
    league = df.get("league_name", pd.Series("", index=df.index)).fillna("")
    in_top_league = league.isin(TOP_LEAGUES)
    df["league_transition_risk"] = (~in_top_league).astype(float) * 40

    # --- Data reliability risk: how much of this player's row is missing ---
    key_cols = [c for c in [
        "per_90_minutes_gls", "per_90_minutes_ast", "per_90_minutes_prg_c",
        "per_90_minutes_tackles_tkl", "value_eur",
    ] if c in df.columns]
    if key_cols:
        missing_ratio = df[key_cols].isna().mean(axis=1)
        df["data_reliability_risk"] = (missing_ratio * 100).round(1)
    else:
        df["data_reliability_risk"] = 0.0

    components = ["age_risk", "availability_risk", "league_transition_risk", "data_reliability_risk"]
    weights = {"age_risk": 0.30, "availability_risk": 0.30, "league_transition_risk": 0.20, "data_reliability_risk": 0.20}

    df["recruitment_risk_score"] = sum(df[c] * w for c, w in weights.items()).round(1)
    # Tier cuts calibrated to this dataset's observed risk-score distribution
    # (roughly the 75th and 95th percentiles) rather than an arbitrary
    # absolute scale, since the component weights above are themselves a
    # judgment call and shouldn't be double-arbitrary with the cut points too.
    df["recruitment_risk_tier"] = pd.cut(
        df["recruitment_risk_score"], bins=[-1, 23, 35, 101], labels=["LOW", "MEDIUM", "HIGH"]
    )

    return df
