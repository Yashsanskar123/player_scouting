"""Composite data quality scoring, replacing the old lightweight
`data_quality_report`. Produces a 0-100 score broken into the four
dimensions the spec calls for: completeness, consistency, validity,
uniqueness. Freshness is reported separately since it depends on how the
platform is deployed (how old is the newest season), not on the data
itself.

No row is ever silently dropped by this module -- it only measures and
reports.
"""
from __future__ import annotations

import pandas as pd

# Sanity bounds for well-known columns; used for the "validity" dimension.
VALID_RANGES = {
    "overall": (1, 99),
    "potential": (1, 99),
    "age_fifa": (14, 50),
    "weak_foot": (1, 5),
    "skill_moves": (1, 5),
    "international_reputation": (1, 5),
    "height_cm": (140, 220),
    "weight_kg": (40, 130),
}


def _completeness(df: pd.DataFrame) -> tuple[float, dict]:
    total_cells = df.shape[0] * df.shape[1]
    missing = int(df.isna().sum().sum())
    ratio = 1 - (missing / total_cells) if total_cells else 0
    return ratio * 100, {"missing_cells": missing, "total_cells": int(total_cells)}


def _uniqueness(df: pd.DataFrame) -> tuple[float, dict]:
    dupe_rows = int(df.duplicated().sum())
    ratio = 1 - (dupe_rows / len(df)) if len(df) else 1
    detail = {"duplicate_rows": dupe_rows}
    if "player_id" in df.columns and "season" in df.columns:
        id_season_dupes = int(df.duplicated(subset=["player_id", "season"]).sum())
        detail["player_id_season_collisions"] = id_season_dupes
        ratio = min(ratio, 1 - (id_season_dupes / len(df)) if len(df) else 1)
    return ratio * 100, detail


def _validity(df: pd.DataFrame) -> tuple[float, dict]:
    violations = {}
    total_checked = 0
    total_violations = 0
    for col, (lo, hi) in VALID_RANGES.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        non_null = series.dropna()
        if non_null.empty:
            continue
        bad = int(((non_null < lo) | (non_null > hi)).sum())
        violations[col] = bad
        total_checked += len(non_null)
        total_violations += bad
    ratio = 1 - (total_violations / total_checked) if total_checked else 1
    return ratio * 100, {"range_violations": violations}


def _consistency(df: pd.DataFrame) -> tuple[float, dict]:
    """Cross-field consistency: e.g. age_fifa vs age_fbref should roughly
    agree; position_data_conflict flag (FIFA vs FBref position bucket).
    """
    detail = {}
    total_checked = 0
    total_conflicts = 0

    if {"age_fifa", "age_fbref"}.issubset(df.columns):
        a = pd.to_numeric(df["age_fifa"], errors="coerce")
        b = pd.to_numeric(df["age_fbref"], errors="coerce")
        both = a.notna() & b.notna()
        conflict = both & ((a - b).abs() > 1)
        detail["age_fifa_vs_age_fbref_conflicts"] = int(conflict.sum())
        total_checked += int(both.sum())
        total_conflicts += int(conflict.sum())

    if "position_data_conflict" in df.columns:
        conflicts = int(df["position_data_conflict"].sum())
        detail["fifa_vs_fbref_position_conflicts"] = conflicts
        total_checked += len(df)
        total_conflicts += conflicts

    ratio = 1 - (total_conflicts / total_checked) if total_checked else 1
    return ratio * 100, detail


def data_quality_score(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"overall_score": 0.0, "breakdown": {}, "issues": ["Dataset is empty."]}

    completeness, completeness_detail = _completeness(df)
    uniqueness, uniqueness_detail = _uniqueness(df)
    validity, validity_detail = _validity(df)
    consistency, consistency_detail = _consistency(df)

    weights = {"completeness": 0.30, "consistency": 0.25, "validity": 0.25, "uniqueness": 0.20}
    overall = (
        completeness * weights["completeness"]
        + consistency * weights["consistency"]
        + validity * weights["validity"]
        + uniqueness * weights["uniqueness"]
    )

    return {
        "overall_score": round(overall, 1),
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "breakdown": {
            "completeness": {"score": round(completeness, 1), **completeness_detail},
            "consistency": {"score": round(consistency, 1), **consistency_detail},
            "validity": {"score": round(validity, 1), **validity_detail},
            "uniqueness": {"score": round(uniqueness, 1), **uniqueness_detail},
        },
        "weights_used": weights,
    }
