"""Transfer-market intelligence built only from fields available in ScoutIQ.

This module deliberately does NOT fabricate contract expiry dates, release clauses,
transfer fees, or negotiation terms. The current FIFA/FBref dataset contains
market value and wage data plus season-to-season club/league history, so those
signals are used transparently and the unavailable contract fields are surfaced
as data gaps.
"""
from __future__ import annotations

import math
import pandas as pd


def _num(row: pd.Series, key: str) -> float | None:
    value = row.get(key)
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_gap(value_gap_pct: float | None) -> float | None:
    if value_gap_pct is None:
        return None
    # +50% or more is treated as a strong positive value signal; negative gaps
    # are retained rather than clipped away so the explanation remains honest.
    return float(max(0.0, min(100.0, 50.0 + value_gap_pct)))


def build_transfer_intelligence(df: pd.DataFrame, player_id: str, season: int | None = None) -> dict:
    if df.empty or "player_id" not in df.columns:
        raise ValueError("No player data loaded")
    matches = df[df["player_id"] == player_id].sort_values("season")
    if matches.empty:
        raise ValueError(f"No player found with player_id '{player_id}'")

    if season is not None:
        selected = matches[matches["season"] == int(season)]
        if selected.empty:
            raise ValueError(f"No player found with player_id '{player_id}' in season {season}")
        row = selected.iloc[-1]
    else:
        row = matches.iloc[-1]
    market_value = _num(row, "value_eur")
    fair_value = _num(row, "fair_value_eur")
    value_gap_pct = _num(row, "value_gap_pct")
    wage = _num(row, "wage_eur")
    performance = _num(row, "performance_score")
    potential = _num(row, "development_potential")
    age = _num(row, "age_fifa")
    risk = _num(row, "recruitment_risk_score")

    wage_to_value_pct = None
    if wage is not None and market_value and market_value > 0:
        wage_to_value_pct = wage / market_value * 100.0

    clubs = [str(x) for x in matches.get("club_name", pd.Series(dtype=object)).dropna().tolist()]
    leagues = [str(x) for x in matches.get("league_name", pd.Series(dtype=object)).dropna().tolist()]
    club_changes = sum(a != b for a, b in zip(clubs, clubs[1:]))
    league_changes = sum(a != b for a, b in zip(leagues, leagues[1:]))
    recent = matches.tail(3)
    recent_clubs = [str(x) for x in recent.get("club_name", pd.Series(dtype=object)).dropna().tolist()]
    recent_movement = sum(a != b for a, b in zip(recent_clubs, recent_clubs[1:]))

    components: dict[str, float] = {}
    gap_score = _score_gap(value_gap_pct)
    if gap_score is not None:
        components["value_leverage"] = gap_score
    if wage_to_value_pct is not None:
        # Lower annual wage relative to market value is a positive affordability signal.
        components["wage_efficiency"] = max(0.0, min(100.0, 100.0 - wage_to_value_pct * 10.0))
    if performance is not None:
        components["current_performance"] = max(0.0, min(100.0, performance))
    if age is not None:
        components["age_profile"] = max(0.0, min(100.0, 100.0 - abs(age - 24.0) * 7.0))
    if risk is not None:
        components["uncertainty"] = max(0.0, min(100.0, 100.0 - risk))

    weights = {
        "value_leverage": 0.35,
        "wage_efficiency": 0.20,
        "current_performance": 0.20,
        "age_profile": 0.10,
        "uncertainty": 0.15,
    }
    available_weight = sum(weights[k] for k in components)
    opportunity_score = None
    if available_weight > 0:
        opportunity_score = sum(components[k] * weights[k] for k in components) / available_weight

    strengths: list[str] = []
    concerns: list[str] = []
    if value_gap_pct is not None:
        if value_gap_pct >= 20:
            strengths.append(f"Model fair value is {value_gap_pct:.0f}% above the current market-value signal")
        elif value_gap_pct < 0:
            concerns.append(f"Model fair value is {abs(value_gap_pct):.0f}% below the current market-value signal")
    if wage_to_value_pct is not None and wage_to_value_pct <= 5:
        strengths.append("Wage burden is relatively light versus market value")
    if age is not None and age <= 23:
        strengths.append("Young age profile supports longer-term squad planning")
    if performance is not None and performance >= 80:
        strengths.append("Current performance is in the strong range")
    if risk is not None and risk >= 35:
        concerns.append("High outcome volatility requires additional scouting validation")
    if league_changes:
        concerns.append(f"Observed {league_changes} league transition(s); adaptation context should be reviewed")
    if recent_movement:
        strengths.append(f"Observed {recent_movement} club move(s) across the latest three seasons")

    data_available = {
        "market_value": market_value is not None,
        "fair_value": fair_value is not None,
        "wage": wage is not None,
        "contract_expiry": False,
        "release_clause": False,
        "transfer_fee": False,
    }
    evidence_coverage = sum(data_available.values()) / len(data_available) * 100.0

    return {
        "player_id": player_id,
        "season": row.get("season"),
        "market_value_eur": market_value,
        "fair_value_eur": fair_value,
        "value_gap_pct": value_gap_pct,
        "wage_eur": wage,
        "wage_to_value_pct": wage_to_value_pct,
        "performance_score": performance,
        "development_potential": potential,
        "age": age,
        "recruitment_risk_score": risk,
        "opportunity_score": round(opportunity_score, 1) if opportunity_score is not None else None,
        "components": {k: round(v, 1) for k, v in components.items()},
        "club_changes": int(club_changes),
        "league_changes": int(league_changes),
        "recent_club_moves": int(recent_movement),
        "contract_status": "UNAVAILABLE",
        "contract_expiry": None,
        "release_clause_eur": None,
        "last_observed_club": row.get("club_name"),
        "last_observed_league": row.get("league_name"),
        "data_available": data_available,
        "evidence_coverage_pct": round(evidence_coverage, 1),
        "strengths": strengths[:4],
        "concerns": concerns[:4],
        "note": "Transfer fee, contract expiry and release-clause data are not present in the current FIFA/FBref dataset. Opportunity score uses only observable market, wage, performance, age, risk and historical-movement signals; it is not a predicted negotiated transfer fee.",
    }
