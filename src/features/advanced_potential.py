"""Advanced potential / trajectory layer.

This module deliberately separates validated forecasting from exploratory
upside signals:

* 12M expected performance reuses the walk-forward-validated recency/mean
  blend from ``potential.py``.
* 24M projection is an exploratory recursive extension of that validated
  estimator; it is labelled as such until a two-step backtest validates it.
* Peak projection is an exploratory ceiling signal combining the player's
  current ability, age room and the FIFA potential benchmark. It is not a
  claim about a player's actual career peak.
* Breakout probability is an empirical historical rate from comparable
  age/direction cohorts, not a trained probability model. It includes the
  cohort sample size so users can judge evidence strength.
* Decline risk is an empirical historical rate for a meaningful next-season
  performance drop and is distinct from the existing recruitment-risk model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.potential import RECENCY_WEIGHT, _age_prior

BREAKOUT_DELTA = 5.0
DECLINE_DELTA = -5.0
MIN_COHORT = 30


def _trajectory_forecast(values: np.ndarray, steps: int = 1) -> float | None:
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return None
    last = float(values[-1])
    mean = float(values.mean())
    forecast = RECENCY_WEIGHT * last + (1 - RECENCY_WEIGHT) * mean
    for _ in range(max(0, steps - 1)):
        forecast = RECENCY_WEIGHT * forecast + (1 - RECENCY_WEIGHT) * mean
    return float(np.clip(forecast, 0, 100))


def _age_band(age: float) -> str:
    if pd.isna(age):
        return "unknown"
    age = float(age)
    if age <= 20:
        return "u21"
    if age <= 23:
        return "21-23"
    if age <= 26:
        return "24-26"
    if age <= 30:
        return "27-30"
    return "31+"


def _direction(values: np.ndarray) -> str:
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return "unknown"
    delta = float(values[-1] - values[-2])
    if delta >= 3:
        return "rising"
    if delta <= -3:
        return "falling"
    return "stable"


def _build_empirical_rates(df: pd.DataFrame) -> dict[tuple[str, str], dict[str, float]]:
    rows: list[dict] = []
    for _, g in df.groupby("player_id"):
        g = g.sort_values("season")
        y = pd.to_numeric(g["performance_score"], errors="coerce").to_numpy()
        ages = pd.to_numeric(g.get("age_fifa"), errors="coerce").to_numpy()
        for i in range(len(g) - 1):
            if np.isnan(y[i]) or np.isnan(y[i + 1]):
                continue
            direction = _direction(y[: i + 1])
            band = _age_band(ages[i]) if i < len(ages) else "unknown"
            rows.append({
                "age_band": band,
                "direction": direction,
                "breakout": float(y[i + 1] - y[i] >= BREAKOUT_DELTA),
                "decline": float(y[i + 1] - y[i] <= DECLINE_DELTA),
            })
    if not rows:
        return {}
    hist = pd.DataFrame(rows)
    rates: dict[tuple[str, str], dict[str, float]] = {}
    for (band, direction), g in hist.groupby(["age_band", "direction"]):
        rates[(band, direction)] = {
            "breakout_probability": float(g["breakout"].mean()),
            "decline_probability": float(g["decline"].mean()),
            "sample_size": int(len(g)),
        }
    return rates


def compute_advanced_potential(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["potential_12m"] = pd.to_numeric(result["expected_performance_12m"], errors="coerce") if "expected_performance_12m" in result.columns else np.nan
    result["potential_12m"] = result["potential_12m"].astype(float)
    result["potential_24m"] = np.nan
    result["peak_projection"] = np.nan
    result["development_trajectory"] = "unknown"
    result["breakout_probability"] = np.nan
    result["decline_probability"] = np.nan
    result["potential_evidence_sample"] = 0
    result["potential_projection_status"] = "exploratory"

    if "player_id" not in result.columns or "season" not in result.columns or "performance_score" not in result.columns:
        return result

    rates = _build_empirical_rates(result[[c for c in ["player_id", "season", "performance_score", "age_fifa"] if c in result.columns]])
    ages = pd.to_numeric(result["age_fifa"], errors="coerce") if "age_fifa" in result.columns else pd.Series(np.nan, index=result.index)
    current_col = "current_ability" if "current_ability" in result.columns else "performance_score"
    current = pd.to_numeric(result[current_col], errors="coerce")
    fifa_col = "fifa_potential_benchmark" if "fifa_potential_benchmark" in result.columns else ("potential" if "potential" in result.columns else None)
    fifa = pd.to_numeric(result[fifa_col], errors="coerce") if fifa_col else pd.Series(np.nan, index=result.index)

    for player_id, group in result.groupby("player_id"):
        g = group.sort_values("season")
        y = pd.to_numeric(g["performance_score"], errors="coerce").to_numpy()
        valid = y[~np.isnan(y)]
        if len(valid) == 0:
            continue
        forecast12 = _trajectory_forecast(valid, 1)
        forecast24 = _trajectory_forecast(valid, 2)
        last_idx = g.index[-1]
        age = ages.loc[last_idx] if last_idx in ages.index else np.nan
        age_room = _age_prior(age)
        cur = float(current.loc[last_idx]) if pd.notna(current.loc[last_idx]) else float(valid[-1])
        fifa_val = fifa.loc[last_idx] if last_idx in fifa.index else np.nan
        fifa_gap = max(0.0, float(fifa_val) - cur) if pd.notna(fifa_val) else 0.0

        # Exploratory ceiling: deliberately conservative and bounded.
        peak = np.clip(cur + 0.45 * fifa_gap + 4.0 * age_room, 0, 100)
        direction = _direction(valid)
        band = _age_band(age)
        cohort = rates.get((band, direction)) or rates.get((band, "stable")) or rates.get(("unknown", direction))
        if cohort:
            bp = cohort["breakout_probability"]
            dp = cohort["decline_probability"]
            n = cohort["sample_size"]
            if n < MIN_COHORT:
                result.loc[last_idx, "potential_projection_status"] = "low_evidence"
            else:
                result.loc[last_idx, "potential_projection_status"] = "exploratory_empirical"
            result.loc[last_idx, "breakout_probability"] = round(bp * 100, 1)
            result.loc[last_idx, "decline_probability"] = round(dp * 100, 1)
            result.loc[last_idx, "potential_evidence_sample"] = n
        result.loc[last_idx, "potential_12m"] = round(forecast12, 1) if forecast12 is not None else np.nan
        result.loc[last_idx, "potential_24m"] = round(forecast24, 1) if forecast24 is not None else np.nan
        result.loc[last_idx, "peak_projection"] = round(float(peak), 1)
        result.loc[last_idx, "development_trajectory"] = direction

    return result


def backtest_advanced_horizons(df: pd.DataFrame, min_seasons: int = 4) -> dict:
    """Walk-forward evaluation for the one- and two-season projections."""
    if not {"player_id", "season", "performance_score"}.issubset(df.columns):
        raise ValueError("df must contain player_id, season and performance_score")
    records = []
    for pid, group in df.groupby("player_id"):
        g = group.sort_values("season")
        y = pd.to_numeric(g["performance_score"], errors="coerce").to_numpy()
        y = y[~np.isnan(y)]
        if len(y) < min_seasons:
            continue
        for h in (1, 2):
            if len(y) <= h + 1:
                continue
            train = y[:-h]
            actual = y[-h]
            pred = _trajectory_forecast(train, h)
            if pred is not None:
                records.append({"player_id": pid, "horizon": h, "actual": actual, "prediction": pred})
    if not records:
        return {"n": 0}
    r = pd.DataFrame(records)
    out = {"n": len(r), "min_seasons_required": min_seasons}
    for h in (1, 2):
        s = r[r.horizon == h]
        if s.empty:
            continue
        out[f"{h}m_season"] = {"n": int(len(s)), "MAE": round(float((s.actual - s.prediction).abs().mean()), 2), "correlation": round(float(s.actual.corr(s.prediction)), 3)}
    return out
