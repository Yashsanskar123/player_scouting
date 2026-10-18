"""Player Performance Score (spec section 11).

Replaces `overall*0.45 + potential*0.25 + ...` with component scores that
are each built from real percentile-based per-90 data, then aggregated
with position-specific weights -- a winger and a centre-back are not
scored the same way.

All component scores are 0-100 (percentile-based), so the final weighted
sum is also naturally 0-100 with no arbitrary rescaling.
"""
from __future__ import annotations

import pandas as pd

COMPONENT_FEATURES = {
    "attacking": ["per_90_minutes_gls_pctile", "per_90_minutes_x_g_pctile", "per_90_minutes_npx_g_pctile"],
    "chance_creation": ["per_90_minutes_ast_pctile", "per_90_minutes_expected_x_a_pctile",
                         "per_90_minutes_kp_pctile", "sca_sca90_pctile", "gca_gca90_pctile"],
    "passing": ["total_cmppct_pctile", "per_90_minutes_1_3_pctile", "per_90_minutes_ppa_pctile"],
    "progression": ["per_90_minutes_prg_c_pctile", "per_90_minutes_prg_p_pctile", "per_90_minutes_prg_r_pctile"],
    "defending": ["per_90_minutes_tackles_tkl_pctile", "per_90_minutes_int_pctile",
                  "per_90_minutes_clr_pctile", "per_90_minutes_blocks_blocks_pctile"],
    "physical": ["physic"],
    "goalkeeping": ["per_90_minutes_performance_saves_pctile", "performance_savepct_pctile",
                    "performance_cspct_pctile"],
}

# Position-specific weighting of the components above. Every position's
# weights sum to 1.0. A component absent for a position (e.g. goalkeeping
# for a striker) simply isn't weighted -- it is not silently included at 0
# and treated as a penalty.
POSITION_COMPONENT_WEIGHTS = {
    "GK": {"goalkeeping": 0.70, "passing": 0.15, "physical": 0.15},
    "CB": {"defending": 0.45, "passing": 0.20, "progression": 0.15, "physical": 0.20},
    "LB": {"defending": 0.30, "progression": 0.25, "chance_creation": 0.20, "physical": 0.15, "passing": 0.10},
    "RB": {"defending": 0.30, "progression": 0.25, "chance_creation": 0.20, "physical": 0.15, "passing": 0.10},
    "LWB": {"defending": 0.25, "progression": 0.30, "chance_creation": 0.25, "physical": 0.20},
    "RWB": {"defending": 0.25, "progression": 0.30, "chance_creation": 0.25, "physical": 0.20},
    "CDM": {"defending": 0.40, "passing": 0.25, "progression": 0.20, "physical": 0.15},
    "CM": {"passing": 0.25, "progression": 0.25, "chance_creation": 0.20, "defending": 0.20, "physical": 0.10},
    "CAM": {"chance_creation": 0.35, "attacking": 0.25, "passing": 0.20, "progression": 0.20},
    "LW": {"attacking": 0.35, "chance_creation": 0.30, "progression": 0.20, "physical": 0.15},
    "RW": {"attacking": 0.35, "chance_creation": 0.30, "progression": 0.20, "physical": 0.15},
    "ST": {"attacking": 0.50, "chance_creation": 0.20, "physical": 0.20, "passing": 0.10},
    "CF": {"attacking": 0.40, "chance_creation": 0.30, "physical": 0.15, "passing": 0.15},
}


def _component_score(df: pd.DataFrame, features: list[str]) -> pd.Series:
    available = [f for f in features if f in df.columns]
    if not available:
        # float NaN, not pd.NA -- pd.NA forces the column to object dtype,
        # which breaks downstream arithmetic (`vals.fillna(0) * weight`)
        # the moment this component is ever touched again. Only surfaces
        # when a component's underlying columns are entirely absent from
        # the input, which never happens with the full real dataset (all
        # 135+ columns always present) but does for any partial input --
        # found via tests/test_performance_score.py.
        return pd.Series(float("nan"), index=df.index, dtype="float64")
    vals = df[available].apply(pd.to_numeric, errors="coerce")
    return vals.mean(axis=1, skipna=True)


def compute_performance_score(
    df: pd.DataFrame, weights_override: dict[str, dict[str, float]] | None = None
) -> pd.DataFrame:
    """weights_override lets a caller substitute different per-position
    component weights (a dict of {position: {component: weight}}) without
    mutating POSITION_COMPONENT_WEIGHTS -- used by
    src/validation/sensitivity.py. Any position not present in the
    override falls back to the module default.
    """
    df = df.copy()

    for component, features in COMPONENT_FEATURES.items():
        df[f"component_{component}"] = _component_score(df, features)

    position_col = "canonical_position" if "canonical_position" in df.columns else None
    df["performance_score"] = pd.NA

    if position_col is None:
        return df

    position_weights = dict(POSITION_COMPONENT_WEIGHTS)
    if weights_override:
        position_weights.update(weights_override)

    for position, weights in position_weights.items():
        mask = df[position_col] == position
        if not mask.any():
            continue

        weighted_sum = pd.Series(0.0, index=df.index)
        used_weight = pd.Series(0.0, index=df.index)

        for component, weight in weights.items():
            col = f"component_{component}"
            if col not in df.columns:
                continue
            vals = df.loc[mask, col]
            present = vals.notna()
            weighted_sum.loc[mask] += vals.fillna(0) * weight
            used_weight.loc[mask] += present.astype(float) * weight

        total_declared = sum(weights.values())
        # float NaN, not pd.NA: pd.NA forces object dtype, and the
        # `.round(1)` two lines down has no defined behavior for it
        # (TypeError: NAType doesn't define __round__). This is reachable
        # in production too, not just a test artifact -- any row where
        # literally none of a position's weighted components have data
        # ends up with used_weight==0 here, and the result should
        # gracefully become NaN, not crash.
        used_safe = used_weight.replace(0, float("nan"))
        df.loc[mask, "performance_score"] = (weighted_sum.loc[mask] / used_safe.loc[mask] * total_declared).clip(0, 100).round(1)

    return df
