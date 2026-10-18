"""Transparent player-to-system tactical fit scoring.

This is a recruitment-support model, not a claim that we observe a club's full
match model. It translates a selected formation + tactical style into weighted
positional requirements and scores a player's available percentile evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


FORMATION_ROLES: dict[str, list[str]] = {
    "4-3-3": ["GK", "LB", "CB", "CB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"],
    "4-2-3-1": ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "LW", "CAM", "RW", "ST"],
    "4-4-2": ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"],
    "3-4-3": ["GK", "CB", "CB", "CB", "LWB", "CM", "CM", "RWB", "LW", "RW", "ST"],
    "3-5-2": ["GK", "CB", "CB", "CB", "LWB", "CM", "CDM", "CM", "RWB", "ST", "ST"],
}

STYLE_PROFILES: dict[str, dict[str, float]] = {
    "Possession": {
        "progression": 0.25, "passing": 0.25, "creation": 0.18,
        "attacking": 0.12, "defending": 0.10, "physical": 0.10,
    },
    "High Press": {
        "defending": 0.25, "physical": 0.20, "progression": 0.18,
        "creation": 0.14, "passing": 0.13, "attacking": 0.10,
    },
    "Transition": {
        "progression": 0.25, "attacking": 0.22, "physical": 0.18,
        "creation": 0.15, "defending": 0.12, "passing": 0.08,
    },
    "Low Block": {
        "defending": 0.30, "physical": 0.22, "attacking": 0.14,
        "passing": 0.14, "progression": 0.10, "creation": 0.10,
    },
    "Balanced": {
        "progression": 0.18, "passing": 0.18, "creation": 0.16,
        "attacking": 0.16, "defending": 0.16, "physical": 0.16,
    },
}

POSITION_BIASES: dict[str, dict[str, float]] = {
    "GK": {"passing": 1.10, "defending": 1.20, "physical": 0.80},
    "CB": {"defending": 1.25, "passing": 1.10, "physical": 1.05, "progression": 1.10},
    "LB": {"defending": 1.05, "progression": 1.15, "passing": 1.05, "physical": 1.00},
    "RB": {"defending": 1.05, "progression": 1.15, "passing": 1.05, "physical": 1.00},
    "LWB": {"progression": 1.20, "creation": 1.10, "defending": 1.00, "physical": 1.05},
    "RWB": {"progression": 1.20, "creation": 1.10, "defending": 1.00, "physical": 1.05},
    "CDM": {"defending": 1.20, "passing": 1.20, "progression": 1.10, "physical": 1.05},
    "CM": {"passing": 1.15, "progression": 1.10, "creation": 1.05, "physical": 1.00},
    "CAM": {"creation": 1.25, "attacking": 1.10, "progression": 1.05, "passing": 1.05},
    "LW": {"attacking": 1.20, "creation": 1.15, "progression": 1.10, "physical": 0.95},
    "RW": {"attacking": 1.20, "creation": 1.15, "progression": 1.10, "physical": 0.95},
    "LM": {"creation": 1.10, "progression": 1.10, "defending": 0.95, "physical": 1.00},
    "RM": {"creation": 1.10, "progression": 1.10, "defending": 0.95, "physical": 1.00},
    "ST": {"attacking": 1.30, "creation": 1.00, "physical": 1.05, "progression": 1.00},
}

COMPONENTS = {
    "attacking": ["per_90_minutes_gls_pctile", "per_90_minutes_x_g_pctile", "per_90_minutes_npx_g_pctile"],
    "creation": ["per_90_minutes_ast_pctile", "per_90_minutes_expected_x_a_pctile", "per_90_minutes_kp_pctile", "sca_sca90_pctile"],
    "progression": ["per_90_minutes_prg_c_pctile", "per_90_minutes_prg_p_pctile", "per_90_minutes_prg_r_pctile", "per_90_minutes_ppa_pctile"],
    "passing": ["per_90_minutes_total_cmp_pctile", "total_cmppct_pctile", "per_90_minutes_1_3_pctile"],
    "defending": ["per_90_minutes_tackles_tkl_pctile", "per_90_minutes_int_pctile", "per_90_minutes_tkl_int_pctile", "per_90_minutes_blocks_blocks_pctile", "per_90_minutes_clr_pctile"],
    "physical": ["pace", "physic", "defending"],
}


def _mean_available(row: pd.Series, columns: list[str]) -> float | None:
    vals = []
    for col in columns:
        if col in row.index and pd.notna(row[col]):
            try:
                vals.append(float(row[col]))
            except (TypeError, ValueError):
                pass
    return sum(vals) / len(vals) if vals else None


def _component_scores(row: pd.Series) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for name, cols in COMPONENTS.items():
        value = _mean_available(row, cols)
        # Raw FIFA physical/attribute fields are 0-100; percentile fields are
        # also 0-100, so all components are on a common scale.
        out[name] = value
    return out


def _role_for_player(row: pd.Series, requested_role: str | None) -> str:
    if requested_role:
        return requested_role.upper()
    position = str(row.get("canonical_position") or "").upper()
    return position if position in POSITION_BIASES else "CM"


def score_tactical_fit(row: pd.Series, formation: str, style: str, requested_role: str | None = None) -> dict[str, Any]:
    formation = formation if formation in FORMATION_ROLES else "4-3-3"
    style = style if style in STYLE_PROFILES else "Balanced"
    role = _role_for_player(row, requested_role)
    weights = STYLE_PROFILES[style].copy()
    biases = POSITION_BIASES.get(role, {})
    for component, bias in biases.items():
        weights[component] *= bias
    total_weight = sum(weights.values()) or 1.0
    weights = {k: v / total_weight for k, v in weights.items()}

    scores = _component_scores(row)
    evidence = []
    weighted_parts = []
    for component, weight in weights.items():
        value = scores.get(component)
        if value is None:
            continue
        weighted_parts.append(value * weight)
        evidence.append({"component": component, "score": round(value, 1), "weight_pct": round(weight * 100, 1)})

    coverage = sum(weights[k] for k, v in scores.items() if v is not None) * 100
    raw_score = sum(weighted_parts) / max(sum(weights[k] for k, v in scores.items() if v is not None), 1e-9)
    score = round(max(0.0, min(100.0, raw_score)), 1)

    evidence.sort(key=lambda x: x["score"], reverse=True)
    strengths = [e for e in evidence if e["score"] >= 70][:3]
    concerns = [e for e in sorted(evidence, key=lambda x: x["score"]) if e["score"] < 60][:3]
    return {
        "formation": formation,
        "style": style,
        "role": role,
        "system_fit_score": score,
        "evidence_coverage_pct": round(coverage, 1),
        "strengths": strengths,
        "concerns": concerns,
        "component_scores": {k: None if v is None else round(v, 1) for k, v in scores.items()},
        "weights": {k: round(v * 100, 1) for k, v in weights.items()},
        "note": "System fit is a transparent modelled compatibility signal from available player metrics; it is not a substitute for observed tactical/tracking data.",
    }


def tactical_fit_for_dataframe(df: pd.DataFrame, formation: str, style: str, role: str | None = None) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        result = score_tactical_fit(row, formation, style, role)
        rows.append({"player_id": row.get("player_id"), "short_name": row.get("short_name"), **result})
    return pd.DataFrame(rows)
