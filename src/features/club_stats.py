"""Summary statistics for a club's roster in one season (shared by the club overview, comparison and dashboard)."""
from __future__ import annotations

import pandas as pd


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else pd.Series(dtype=float)


def _mean(series: pd.Series, digits: int = 1):
    return round(float(series.mean()), digits) if series.notna().any() else None


def roster_stats(roster: pd.DataFrame) -> dict:
    age, perf = _num(roster, "age_fifa"), _num(roster, "performance_score")
    value = _num(roster, "value_eur")
    by_group = {}
    if "broad_position_group" in roster.columns:
        for group, g in roster.groupby("broad_position_group"):
            by_group[str(group)] = {"players": int(len(g)), "average_performance": _mean(_num(g, "performance_score")), "average_age": _mean(_num(g, "age_fifa"))}
    return {
        "roster_size": int(len(roster)),
        "average_age": _mean(age),
        "average_performance": _mean(perf),
        "squad_market_value_eur": float(value.sum()) if value.notna().any() else None,
        "young_players_share": round(float((age <= 23).mean()) * 100, 0) if age.notna().any() else None,
        "positions": roster["canonical_position"].value_counts().to_dict() if "canonical_position" in roster.columns else {},
        "by_position_group": by_group,
    }
