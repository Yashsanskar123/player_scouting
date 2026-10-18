"""Sample Reliability Score (spec section 6).

Per-90 statistics computed on small minute samples are noisy. This module
scores how much a player's per-90 numbers should be trusted, so downstream
consumers (role fit, scoring, similarity) can discount or flag low-sample
players instead of silently treating 200 minutes the same as 3000.
"""
from __future__ import annotations

import pandas as pd

# Minutes considered a "full" reliable sample for a single season.
FULL_SAMPLE_MINUTES = 1800  # roughly 20 full 90s


def compute_reliability_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    minutes = pd.to_numeric(df.get("playing_time_min", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    starts = pd.to_numeric(df.get("playing_time_starts", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    apps = pd.to_numeric(df.get("playing_time_mp", pd.Series(0, index=df.index)), errors="coerce").fillna(0)

    minutes_component = (minutes / FULL_SAMPLE_MINUTES).clip(0, 1)
    starts_ratio = (starts / apps.replace(0, pd.NA)).fillna(0).clip(0, 1)

    df["sample_reliability_score"] = (minutes_component * 0.75 + starts_ratio * 0.25) * 100
    df["sample_reliability_score"] = df["sample_reliability_score"].round(1)

    df["sample_reliability_tier"] = pd.cut(
        df["sample_reliability_score"],
        bins=[-1, 30, 60, 85, 100],
        labels=["Very Low", "Low", "Moderate", "High"],
    )

    return df
