"""Role archetype definitions and the role-fit engine (spec sections 8-9).

Replaces the old `ROLE_COLUMNS` sum-of-raw-attributes approach with:
  1. Real archetypes per position (not just "ST"), each grounded in
     measurable per-90 / attribute features.
  2. Weighted scoring against PERCENTILE columns (not raw stats), so a
     0-100 fit score is always on a comparable scale regardless of which
     features a role emphasizes.
  3. An explanation: which components pushed the score up or down.

Weights are declared per role, sum to 1.0, and are stored alongside the
score output so a user can see exactly why a number is what it is --
no hidden scaling per spec section 67.
"""
from __future__ import annotations

import pandas as pd

# Each feature must reference a real column: either a percentile column
# produced by features.percentiles (suffix _pctile) or a raw 0-100-ish
# FIFA attribute (used directly, already on a 0-100 scale).
ROLE_ARCHETYPES: dict[str, dict] = {
    # --- Goalkeeper ---
    "Sweeper Keeper": {
        "position_group": "GK",
        "weights": {
            "goalkeeping_kicking": 0.25, "goalkeeping_positioning": 0.20,
            "per_90_minutes_performance_saves_pctile": 0.20,
            "performance_savepct_pctile": 0.20, "pace": 0.15,
        },
    },
    "Traditional Goalkeeper": {
        "position_group": "GK",
        "weights": {
            "goalkeeping_reflexes": 0.30, "goalkeeping_handling": 0.25,
            "performance_savepct_pctile": 0.25, "performance_cspct_pctile": 0.20,
        },
    },
    # --- Centre Back ---
    "Progressive Centre Back": {
        "position_group": "CB",
        "weights": {
            "per_90_minutes_prg_p_pctile": 0.20, "per_90_minutes_prg_c_pctile": 0.15,
            "total_cmppct_pctile": 0.15, "per_90_minutes_tackles_tkl_pctile": 0.15,
            "physic": 0.15, "per_90_minutes_int_pctile": 0.10, "passing": 0.10,
        },
    },
    "Stopper Centre Back": {
        "position_group": "CB",
        "weights": {
            "per_90_minutes_tackles_tkl_w_pctile": 0.25, "per_90_minutes_clr_pctile": 0.20,
            "physic": 0.25, "defending": 0.20, "per_90_minutes_blocks_blocks_pctile": 0.10,
        },
    },
    # --- Fullback ---
    "Attacking Fullback": {
        "position_group": None, "positions": ["LB", "RB", "LWB", "RWB"],
        "weights": {
            "per_90_minutes_crs_pa_pctile": 0.20, "per_90_minutes_ppa_pctile": 0.15,
            "pace": 0.20, "per_90_minutes_prg_c_pctile": 0.20,
            "per_90_minutes_expected_x_a_pctile": 0.15, "dribbling": 0.10,
        },
    },
    "Defensive Fullback": {
        "position_group": None, "positions": ["LB", "RB", "LWB", "RWB"],
        "weights": {
            "per_90_minutes_tackles_tkl_pctile": 0.25, "per_90_minutes_int_pctile": 0.20,
            "defending": 0.25, "physic": 0.15, "pace": 0.15,
        },
    },
    # --- Defensive Midfielder ---
    "Ball-Winning 6": {
        "position_group": "CDM",
        "weights": {
            "per_90_minutes_tackles_tkl_w_pctile": 0.25, "per_90_minutes_int_pctile": 0.20,
            "per_90_minutes_tkl_int_pctile": 0.20, "physic": 0.20, "defending": 0.15,
        },
    },
    "Deep-Lying Playmaker": {
        "position_group": "CDM",
        "weights": {
            "per_90_minutes_prg_p_pctile": 0.25, "total_cmppct_pctile": 0.20,
            "long_cmppct_pctile" if False else "passing": 0.20,  # placeholder overwritten below
            "per_90_minutes_1_3_pctile": 0.20, "vision": 0.0,
        },
    },
    # --- Central Midfielder ---
    "Box-to-Box Midfielder": {
        "position_group": "CM",
        "weights": {
            "per_90_minutes_tackles_tkl_pctile": 0.15, "per_90_minutes_prg_c_pctile": 0.20,
            "per_90_minutes_gls_pctile": 0.15, "physic": 0.20, "dribbling": 0.15,
            "per_90_minutes_ast_pctile": 0.15,
        },
    },
    "Tempo-Controlling Midfielder": {
        "position_group": "CM",
        "weights": {
            "total_cmppct_pctile": 0.30, "per_90_minutes_prg_p_pctile": 0.25,
            "passing": 0.25, "per_90_minutes_1_3_pctile": 0.20,
        },
    },
    # --- Attacking Midfielder ---
    "Creative 10": {
        "position_group": "CAM",
        "weights": {
            "per_90_minutes_kp_pctile": 0.20, "per_90_minutes_expected_x_a_pctile": 0.20,
            "sca_sca90_pctile": 0.20, "dribbling": 0.20, "per_90_minutes_ppa_pctile": 0.20,
        },
    },
    "Shadow Striker": {
        "position_group": "CAM",
        "weights": {
            "per_90_minutes_gls_pctile": 0.30, "per_90_minutes_x_g_pctile": 0.25,
            "gca_gca90_pctile": 0.20, "shooting": 0.15, "dribbling": 0.10,
        },
    },
    # --- Winger ---
    "Inside Forward": {
        "position_group": None, "positions": ["LW", "RW"],
        "weights": {
            "per_90_minutes_x_g_pctile": 0.25, "per_90_minutes_gls_pctile": 0.25,
            "dribbling": 0.20, "shooting": 0.15, "pace": 0.15,
        },
    },
    "Wide Playmaker": {
        "position_group": None, "positions": ["LW", "RW"],
        "weights": {
            "per_90_minutes_kp_pctile": 0.25, "per_90_minutes_crs_pa_pctile": 0.20,
            "per_90_minutes_expected_x_a_pctile": 0.25, "passing": 0.15, "dribbling": 0.15,
        },
    },
    # --- Striker ---
    "Poacher": {
        "position_group": "ST",
        "weights": {
            "per_90_minutes_gls_pctile": 0.35, "per_90_minutes_x_g_pctile": 0.25,
            "standard_g_so_t_pctile" if False else "shooting": 0.20,
            "per_90_minutes_npx_g_pctile": 0.20,
        },
    },
    "Target Forward": {
        "position_group": "ST",
        "weights": {
            "physic": 0.30, "per_90_minutes_gls_pctile": 0.20,
            "per_90_minutes_ast_pctile": 0.15, "shooting": 0.20, "dribbling": 0.15,
        },
    },
    "Complete Forward": {
        "position_group": "ST",
        "weights": {
            "per_90_minutes_gls_pctile": 0.20, "per_90_minutes_ast_pctile": 0.15,
            "per_90_minutes_x_g_pctile": 0.15, "physic": 0.15, "dribbling": 0.15,
            "shooting": 0.10, "passing": 0.10,
        },
    },
}

# fix the accidental `False` conditional-key artifacts above (kept inline
# for readability of intent; cleaned here so weights always sum sanely)
ROLE_ARCHETYPES["Deep-Lying Playmaker"]["weights"] = {
    "per_90_minutes_prg_p_pctile": 0.30, "total_cmppct_pctile": 0.25,
    "passing": 0.25, "per_90_minutes_1_3_pctile": 0.20,
}
ROLE_ARCHETYPES["Poacher"]["weights"] = {
    "per_90_minutes_gls_pctile": 0.35, "per_90_minutes_x_g_pctile": 0.25,
    "shooting": 0.20, "per_90_minutes_npx_g_pctile": 0.20,
}


def _roles_for_position(canonical_position: str) -> list[str]:
    matches = []
    for role, cfg in ROLE_ARCHETYPES.items():
        if cfg.get("position_group") == canonical_position:
            matches.append(role)
        elif canonical_position in (cfg.get("positions") or []):
            matches.append(role)
    return matches


def compute_role_fit(df: pd.DataFrame, role: str, weights_override: dict[str, float] | None = None) -> pd.DataFrame:
    """Score every player (regardless of position) against a named role.
    Scores are still meaningful for out-of-position players -- e.g. a
    CM's fit for 'Ball-Winning 6' -- since role fit and position are
    deliberately decoupled per spec section 8.

    weights_override lets a caller substitute a different weight dict for
    this one call without mutating ROLE_ARCHETYPES -- used by
    src/validation/sensitivity.py to test whether rankings are stable
    under small weight perturbations, without monkeypatching global state.
    """
    if role not in ROLE_ARCHETYPES:
        raise ValueError(f"Unknown role archetype: {role}. Available: {list(ROLE_ARCHETYPES)}")

    weights = weights_override if weights_override is not None else ROLE_ARCHETYPES[role]["weights"]
    total_declared_weight = sum(weights.values())  # scalar constant, e.g. 1.0
    result = df.copy()
    weighted_sum = pd.Series(0.0, index=result.index)
    used_weight = pd.Series(0.0, index=result.index)  # per-row: weight of features actually present for that row

    for feature, weight in weights.items():
        if feature not in result.columns:
            continue
        raw = pd.to_numeric(result[feature], errors="coerce")
        present = raw.notna()
        weighted_sum += raw.fillna(0) * weight
        used_weight += present.astype(float) * weight

    # Renormalize so a row missing some declared features is scored on the
    # weight it DOES have, then rescaled back up to the role's full
    # declared weight -- e.g. if only 80% of a role's weight was
    # available for a player, that 80%-based score is projected back
    # onto the full 0-100 scale rather than silently capped low.
    # float NaN, not pd.NA -- see the identical fix (and explanation) in
    # src/features/performance_score.py, found via the same test bug.
    used_weight_safe = used_weight.replace(0, float("nan"))
    result["role_fit_score"] = (weighted_sum / used_weight_safe * total_declared_weight)
    result["role_fit_score"] = result["role_fit_score"].clip(0, 100).round(1)
    result["role_fit_coverage_pct"] = (used_weight / total_declared_weight * 100).round(1)
    result["role_fit_role"] = role

    return result


def explain_role_fit(row: pd.Series, role: str, top_n: int = 3) -> dict:
    """Return the top positive and negative contributing features for one
    player's role-fit score, in human-readable form.
    """
    weights = ROLE_ARCHETYPES[role]["weights"]
    contributions = []
    for feature, weight in weights.items():
        if feature not in row.index:
            continue
        value = pd.to_numeric(pd.Series([row[feature]]), errors="coerce").iloc[0]
        if pd.isna(value):
            continue
        label = feature.replace("_pctile", "").replace("per_90_minutes_", "").replace("_", " ")
        contributions.append({"feature": label, "value": round(float(value), 1), "weight": weight})

    contributions.sort(key=lambda c: c["value"], reverse=True)
    strengths = [c for c in contributions if c["value"] >= 60][:top_n]
    weaknesses = [c for c in contributions if c["value"] < 40][-top_n:]

    return {
        "role": role,
        "strengths": strengths,
        "limitations": weaknesses,
    }


def recommended_roles_for_position(canonical_position: str) -> list[str]:
    return _roles_for_position(canonical_position)
