import pandas as pd

from src.features.performance_score import compute_performance_score, POSITION_COMPONENT_WEIGHTS


def test_every_position_weight_set_sums_to_one():
    for position, weights in POSITION_COMPONENT_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, f"{position} weights sum to {total}"


def test_striker_and_cb_scored_differently_for_same_inputs():
    # Same raw component scores, different position -> should NOT produce
    # the same performance_score, since ST and CB weight the components
    # completely differently (attacking-heavy vs defending-heavy).
    row = {
        "per_90_minutes_gls_pctile": 90, "per_90_minutes_x_g_pctile": 90, "per_90_minutes_npx_g_pctile": 90,
        "per_90_minutes_tackles_tkl_pctile": 20, "per_90_minutes_int_pctile": 20,
        "per_90_minutes_clr_pctile": 20, "per_90_minutes_blocks_blocks_pctile": 20,
        "physic": 70, "total_cmppct_pctile": 50, "per_90_minutes_1_3_pctile": 50, "per_90_minutes_ppa_pctile": 50,
    }
    df = pd.DataFrame([{**row, "canonical_position": "ST"}, {**row, "canonical_position": "CB"}])
    scored = compute_performance_score(df)
    st_score = scored.loc[scored["canonical_position"] == "ST", "performance_score"].iloc[0]
    cb_score = scored.loc[scored["canonical_position"] == "CB", "performance_score"].iloc[0]
    assert st_score > cb_score, "a player with elite attacking + weak defending stats should score higher as a ST than a CB"


def test_performance_score_bounded_0_100(pipeline_df):
    valid = pipeline_df["performance_score"].dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_unknown_position_gets_no_score():
    df = pd.DataFrame([{"canonical_position": "NOT_A_POSITION", "component_attacking": 90}])
    scored = compute_performance_score(df)
    assert pd.isna(scored.loc[0, "performance_score"])


def test_weights_override_only_affects_specified_position():
    df = pd.DataFrame([
        {
            "canonical_position": "ST",
            "per_90_minutes_gls_pctile": 90, "per_90_minutes_x_g_pctile": 90, "per_90_minutes_npx_g_pctile": 90,
            "physic": 10,
        },
        {
            "canonical_position": "CB",
            "per_90_minutes_tackles_tkl_pctile": 90, "per_90_minutes_int_pctile": 90,
            "per_90_minutes_clr_pctile": 90, "per_90_minutes_blocks_blocks_pctile": 90,
            "physic": 10,
        },
    ])
    baseline = compute_performance_score(df)
    overridden = compute_performance_score(df, weights_override={"ST": {"physical": 1.0}})
    st_baseline = baseline.loc[baseline["canonical_position"] == "ST", "performance_score"].iloc[0]
    st_overridden = overridden.loc[overridden["canonical_position"] == "ST", "performance_score"].iloc[0]
    cb_baseline = baseline.loc[baseline["canonical_position"] == "CB", "performance_score"].iloc[0]
    cb_overridden = overridden.loc[overridden["canonical_position"] == "CB", "performance_score"].iloc[0]
    assert st_baseline != st_overridden, "overriding ST to weight only physical (low=10) should pull its score down from the attacking-heavy baseline"
    assert cb_baseline == cb_overridden, "overriding ST weights must not affect CB scoring"


def test_zero_available_weighted_components_degrades_to_nan_not_crash():
    # Regression test: found via a test typo that turned out to expose a
    # real bug -- when a weights_override points entirely at component
    # names that have no data for a row, the old code crashed inside
    # .round(1) with "TypeError: NAType doesn't define __round__" instead
    # of gracefully leaving performance_score as NaN for that row.
    df = pd.DataFrame([{"canonical_position": "ST", "physic": 10}])
    result = compute_performance_score(df, weights_override={"ST": {"nonexistent_component": 1.0}})
    assert pd.isna(result.loc[0, "performance_score"])
