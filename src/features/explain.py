"""Plain-language, exactly-reconciling explanations of a player's model outputs.

Every breakdown below is recomputed from the same formulas the pipeline uses
(performance_score.py, risk.py, potential.py) and is checked against the stored
number: `reconciles` is True only when the parts add back up to it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.performance_score import COMPONENT_FEATURES, POSITION_COMPONENT_WEIGHTS
from src.features.potential import _age_prior
from src.reports.common import percentile_label

COMPONENT_LABELS = {"attacking": "Attacking", "chance_creation": "Chance creation", "passing": "Passing", "progression": "Progression",
                    "defending": "Defending", "physical": "Physical", "goalkeeping": "Goalkeeping"}
RISK_WEIGHTS = {"age_risk": 0.30, "availability_risk": 0.30, "league_transition_risk": 0.20, "data_reliability_risk": 0.20}
RISK_LABELS = {"age_risk": "Age (very young or ageing)", "availability_risk": "Small or uneven playing sample",
               "league_transition_risk": "Outside the top-5 leagues (adaptation)", "data_reliability_risk": "Missing statistics"}


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(x) else x


def _r(v, d=1):
    x = _f(v)
    return None if x is None else round(x, d)


def explain_performance(row: dict, peers: pd.DataFrame | None) -> dict:
    position = row.get("canonical_position")
    weights = POSITION_COMPONENT_WEIGHTS.get(position)
    score = _f(row.get("performance_score"))
    if not weights or score is None:
        return {"available": False, "reason": "No performance score for this player and season."}
    values = {c: _f(row.get(f"component_{c}")) for c in weights}
    used = sum(w for c, w in weights.items() if values[c] is not None)
    comps, missing = [], []
    for comp, w in weights.items():
        v = values[comp]
        if v is None:
            missing.append(COMPONENT_LABELS[comp])
            continue
        contrib = w * v / used
        evidence = [{"label": percentile_label(f.replace("_pctile", "")), "percentile": _r(row.get(f))}
                    for f in COMPONENT_FEATURES[comp] if _f(row.get(f)) is not None]
        comps.append({"key": comp, "label": COMPONENT_LABELS[comp], "value": _r(v), "declared_weight": w, "effective_weight": round(w / used, 3),
                      "contribution": round(contrib, 2), "evidence": evidence})
    comps.sort(key=lambda c: -c["contribution"])
    rebuilt = round(float(np.clip(sum(c["contribution"] for c in comps), 0, 100)), 1)
    adj, adjusted = _f(row.get("league_strength_adjustment")), _f(row.get("adjusted_performance_score"))
    out = {"available": True, "position": position, "score": _r(score), "components": comps, "missing_components": missing,
           "reconstructed_score": rebuilt, "reconciles": abs(rebuilt - score) <= 0.15,
           "strengths": [c["label"] for c in sorted(comps, key=lambda c: -c["value"])[:2] if c["value"] >= 60],
           "weak_spots": [c["label"] for c in sorted(comps, key=lambda c: c["value"])[:2] if c["value"] < 50],
           "league": {"league_name": row.get("league_name"), "adjustment_points": _r(adj, 2) if adj is None else _r(-adj, 2), "adjusted_score": _r(adjusted),
                      "reconciles": None if adj is None or adjusted is None else abs(float(np.clip(score - adj, 0, 100)) - adjusted) <= 0.15}}
    if peers is not None and len(peers) >= 10:
        ps = pd.to_numeric(peers["performance_score"], errors="coerce").dropna()
        out["versus_peers"] = {"n": int(len(ps)), "position_average": _r(ps.mean()), "difference": _r(score - ps.mean()), "percentile": _r((ps < score).mean() * 100, 0)}
    return out


def explain_risk(row: dict) -> dict:
    parts = {k: _f(row.get(k)) for k in RISK_WEIGHTS}
    score = _f(row.get("recruitment_risk_score"))
    if score is None or any(v is None for v in parts.values()):
        return {"available": False}
    comps = [{"key": k, "label": RISK_LABELS[k], "value": _r(v), "weight": RISK_WEIGHTS[k], "contribution": round(v * RISK_WEIGHTS[k], 2)} for k, v in parts.items()]
    rebuilt = round(sum(c["contribution"] for c in comps), 1)
    return {"available": True, "score": _r(score), "tier": row.get("recruitment_risk_tier"), "components": sorted(comps, key=lambda c: -c["contribution"]),
            "reconstructed_score": rebuilt, "reconciles": abs(rebuilt - score) <= 0.15,
            "meaning": "How uncertain this player's next season is. It is a volatility indicator; it does not predict that he will get worse."}


def explain_potential(row: dict) -> dict:
    current, age, fifa = _f(row.get("current_ability")) or _f(row.get("performance_score")), _f(row.get("age_fifa")), _f(row.get("fifa_potential_benchmark")) or _f(row.get("potential"))
    dev = _f(row.get("development_potential"))
    if current is None or dev is None:
        return {"available": False}
    room = _age_prior(age if age is not None else float("nan"))
    gap = max(0.0, fifa - current) if fifa is not None else 0.0
    parts = [{"label": "Current performance", "points": round(current, 2)}, {"label": f"Age room (age {int(age) if age is not None else '?'})", "points": round(room * 15 * 0.5, 2)},
             {"label": "Half of the FIFA potential gap", "points": round(gap * 0.5, 2)}]
    rebuilt = round(float(np.clip(sum(p["points"] for p in parts), 0, 100)), 1)
    return {"available": True, "development_potential": _r(dev), "components": parts, "reconstructed": rebuilt, "reconciles": abs(rebuilt - dev) <= 0.15,
            "expected_12m": _r(row.get("expected_performance_12m")), "expected_12m_method": row.get("trend_source"),
            "peak_projection": _r(row.get("peak_projection")), "breakout_probability": _r(row.get("breakout_probability")),
            "decline_probability": _r(row.get("decline_probability")), "cohort_sample": int(_f(row.get("potential_evidence_sample")) or 0),
            "projection_status": row.get("potential_projection_status"),
            "note": "Development potential is an upside ceiling, not a forecast of next season."}


def explain_value(row: dict, peers: pd.DataFrame | None) -> dict:
    market, fair = _f(row.get("value_eur")), _f(row.get("fair_value_eur"))
    if market is None or fair is None:
        return {"available": False}
    out = {"available": True, "market_value_eur": market, "fair_value_eur": fair, "gap_eur": fair - market,
           "gap_pct": _r(row.get("value_gap_pct")),
           "how": "Fair value is a model estimate of what a player with this profile is worth; it follows FIFA's own valuation closely, so the gap compares the model with FIFA's number, not with the transfer market."}
    age, perf = _f(row.get("age_fifa")), _f(row.get("performance_score"))
    if peers is not None and age is not None and perf is not None:
        ages, perfs = pd.to_numeric(peers["age_fifa"], errors="coerce"), pd.to_numeric(peers["performance_score"], errors="coerce")
        near = peers[(ages - age).abs().le(2) & (perfs - perf).abs().le(5) & (peers["player_id"] != row.get("player_id"))]
        vals = pd.to_numeric(near["value_eur"], errors="coerce").dropna()
        if len(vals) >= 5:
            out["comparable_players"] = {"n": int(len(vals)), "median_value_eur": float(vals.median()), "low_eur": float(vals.quantile(0.25)), "high_eur": float(vals.quantile(0.75)),
                                         "definition": "Same position and season, age within 2 years, performance within 5 points."}
    return out


def explain_player(row: dict, season_peers: pd.DataFrame | None, statuses: dict | None = None) -> dict:
    peers = None
    if season_peers is not None and "canonical_position" in season_peers.columns:
        peers = season_peers[season_peers["canonical_position"] == row.get("canonical_position")]
    return {"player_id": row.get("player_id"), "short_name": row.get("short_name"), "season": row.get("season"),
            "performance": explain_performance(row, peers), "value": explain_value(row, peers), "risk": explain_risk(row),
            "potential": explain_potential(row),
            "reliability": {"score": _r(row.get("sample_reliability_score")), "tier": row.get("sample_reliability_tier"), "minutes": _r(row.get("playing_time_min"), 0)},
            "validation": statuses or {}}
