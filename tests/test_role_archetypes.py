import pandas as pd

from src.features.role_archetypes import (
    compute_role_fit, explain_role_fit, recommended_roles_for_position, ROLE_ARCHETYPES,
)


def test_every_declared_role_weight_set_sums_to_one():
    for role, cfg in ROLE_ARCHETYPES.items():
        total = sum(cfg["weights"].values())
        assert abs(total - 1.0) < 0.01, f"{role} weights sum to {total}, not 1.0"


def test_role_fit_not_uniformly_maxed_out(pipeline_df):
    # Regression test: an earlier version of this renormalization logic
    # had a bug (dividing by a per-row weight then multiplying by a
    # column-summed constant instead of the scalar total declared
    # weight) that caused every player to score exactly 100.0 regardless
    # of their actual stats. Assert real variance exists instead.
    scored = compute_role_fit(pipeline_df[pipeline_df["canonical_position"] == "ST"], "Poacher")
    scores = scored["role_fit_score"].dropna()
    assert scores.nunique() > 1, "all players scored identically -- renormalization bug regression"
    assert scores.std() > 1.0


def test_role_fit_ranks_higher_scorer_above_lower_scorer(pipeline_df):
    strikers = pipeline_df[pipeline_df["canonical_position"] == "ST"]
    scored = compute_role_fit(strikers, "Poacher")
    ranked = scored.sort_values("role_fit_score", ascending=False)
    # Striker 0 has the highest goals/xG in the fixture data -- should rank first for Poacher.
    assert ranked.iloc[0]["short_name"] == "Striker 0"


def test_role_fit_score_bounded_0_100(pipeline_df):
    for role in ["Poacher", "Progressive Centre Back"]:
        pool = pipeline_df[pipeline_df["canonical_position"].isin(["ST", "CB"])]
        scored = compute_role_fit(pool, role)
        valid = scored["role_fit_score"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()


def test_unknown_role_raises():
    df = pd.DataFrame([{"physic": 70}])
    try:
        compute_role_fit(df, "Not A Real Role")
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_weights_override_changes_score_without_mutating_global_state():
    df = pd.DataFrame([{"physic": 80, "per_90_minutes_gls_pctile": 20, "shooting": 40, "per_90_minutes_npx_g_pctile": 20}])
    baseline = compute_role_fit(df, "Poacher")
    overridden = compute_role_fit(df, "Poacher", weights_override={"physic": 1.0})
    assert baseline.loc[0, "role_fit_score"] != overridden.loc[0, "role_fit_score"]
    # global ROLE_ARCHETYPES must be unchanged after using an override
    assert "physic" not in ROLE_ARCHETYPES["Poacher"]["weights"] or ROLE_ARCHETYPES["Poacher"]["weights"].get("physic") != 1.0


def test_missing_features_renormalize_not_silently_penalize():
    # A row missing half the role's declared features should still be
    # scored on a 0-100 scale using what IS present, not dragged toward
    # zero just because some features are missing (see role_archetypes.py
    # renormalization comment).
    full_row = pd.DataFrame([{
        "per_90_minutes_gls_pctile": 90, "per_90_minutes_x_g_pctile": 90,
        "shooting": 90, "per_90_minutes_npx_g_pctile": 90,
    }])
    partial_row = pd.DataFrame([{
        "per_90_minutes_gls_pctile": 90,  # only one of four Poacher features present
    }])
    full_score = compute_role_fit(full_row, "Poacher").loc[0, "role_fit_score"]
    partial_score = compute_role_fit(partial_row, "Poacher").loc[0, "role_fit_score"]
    assert abs(full_score - partial_score) < 5, "renormalization should put both near the same scale given equally-strong available signal"


def test_explain_role_fit_separates_strengths_and_limitations():
    row = pd.Series({
        "per_90_minutes_gls_pctile": 95, "per_90_minutes_x_g_pctile": 90,
        "shooting": 85, "per_90_minutes_npx_g_pctile": 20,
    })
    explanation = explain_role_fit(row, "Poacher")
    strength_features = {s["feature"] for s in explanation["strengths"]}
    limitation_features = {s["feature"] for s in explanation["limitations"]}
    assert "gls" in strength_features
    assert "npx g" in limitation_features


def test_recommended_roles_for_position_returns_only_applicable_roles():
    st_roles = recommended_roles_for_position("ST")
    assert "Poacher" in st_roles
    assert "Deep-Lying Playmaker" not in st_roles


def test_zero_available_weighted_features_degrades_to_nan_not_crash():
    # Regression test: the identical pd.NA-dtype-poisoning bug fixed in
    # performance_score.py existed here too (used_weight.replace(0, pd.NA)
    # crashing .round(1) with NAType has no __round__). A row with none
    # of a role's weighted features present should score NaN, not crash.
    df = pd.DataFrame([{"physic": 70}])  # no Poacher-relevant columns at all
    result = compute_role_fit(df, "Poacher", weights_override={"totally_absent_feature": 1.0})
    assert pd.isna(result.loc[0, "role_fit_score"])
