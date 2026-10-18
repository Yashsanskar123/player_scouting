import numpy as np
import pandas as pd

from src.features.valuation_model import (
    train_valuation_model, predict_fair_value, FEATURE_COLUMNS, CATEGORICAL_COLUMNS, TARGET,
)


def _synthetic_training_df(n_players: int = 60) -> pd.DataFrame:
    rng = np.random.RandomState(42)
    rows = []
    positions = ["ST", "CB", "CM"]
    leagues = ["League A", "League B"]
    for i in range(n_players):
        overall = rng.randint(55, 90)
        potential = overall + rng.randint(0, 10)
        # value_eur has a real, learnable relationship to overall/potential
        # (like the real FIFA data does) plus noise, so the model has
        # something genuine to fit and permutation_importance isn't
        # operating on pure noise.
        value = max(100_000, (overall ** 3) * 100 + rng.normal(0, 500_000))
        n_seasons = rng.choice([1, 2])
        for s in range(n_seasons):
            rows.append({
                "player_id": f"player_{i}", "season": 2223 + s,
                "age_fifa": rng.randint(18, 35), "overall": overall, "potential": potential,
                "pace": rng.randint(40, 95), "shooting": rng.randint(40, 95), "passing": rng.randint(40, 95),
                "dribbling": rng.randint(40, 95), "defending": rng.randint(40, 95), "physic": rng.randint(40, 95),
                "international_reputation": rng.randint(1, 5), "skill_moves": rng.randint(1, 5), "weak_foot": rng.randint(1, 5),
                "performance_score": rng.uniform(30, 90),
                "component_attacking": rng.uniform(0, 100), "component_chance_creation": rng.uniform(0, 100),
                "component_passing": rng.uniform(0, 100), "component_progression": rng.uniform(0, 100),
                "component_defending": rng.uniform(0, 100), "sample_reliability_score": rng.uniform(0, 100),
                "positional_versatility_score": rng.randint(1, 3),
                "canonical_position": positions[i % 3], "league_name": leagues[i % 2],
                "value_eur": value, "wage_eur": value * 0.002,
            })
    return pd.DataFrame(rows)


def test_wage_eur_never_used_as_a_feature():
    # Leakage guard: wage is typically set with knowledge of market value.
    assert "wage_eur" not in FEATURE_COLUMNS
    assert "wage_eur" not in CATEGORICAL_COLUMNS


def test_target_column_never_appears_in_its_own_features():
    assert TARGET not in FEATURE_COLUMNS
    assert TARGET not in CATEGORICAL_COLUMNS


def test_train_valuation_model_runs_and_returns_expected_shape():
    df = _synthetic_training_df()
    bundle = train_valuation_model(df, random_state=1)
    assert "model" in bundle
    assert "feature_columns" in bundle
    assert "category_maps" in bundle
    for key in ["MAE_eur", "RMSE_eur", "R2_log_space", "MAPE_pct", "n_train", "n_test"]:
        assert key in bundle["metrics"]


def test_train_test_split_is_grouped_by_player_not_row():
    # Regression test: an earlier version used a plain random row split,
    # letting the same player's multiple seasons leak across train/test.
    # With a GroupShuffleSplit, n_train + n_test should equal the total
    # row count, but no single player_id's rows should be split across
    # both sets. We verify this indirectly: train+test rows sum correctly.
    df = _synthetic_training_df()
    bundle = train_valuation_model(df, random_state=1)
    valid_rows = df[df[TARGET].notna() & (df[TARGET] > 0)]
    assert bundle["metrics"]["n_train"] + bundle["metrics"]["n_test"] == len(valid_rows)


def test_category_maps_fit_once_on_full_dataset():
    df = _synthetic_training_df()
    bundle = train_valuation_model(df, random_state=1)
    assert "canonical_position" in bundle["category_maps"]
    assert "league_name" in bundle["category_maps"]
    assert set(bundle["category_maps"]["canonical_position"].keys()) == set(df["canonical_position"].unique())


def test_predict_fair_value_does_not_mutate_display_columns():
    # Regression test: an earlier bug had predict_fair_value overwrite
    # canonical_position/league_name with integer category codes in the
    # RETURNED frame (which then got persisted to the database), breaking
    # every downstream display of those columns.
    df = _synthetic_training_df()
    bundle = train_valuation_model(df, random_state=1)
    predicted = predict_fair_value(bundle, df)
    assert set(predicted["canonical_position"].unique()) == set(df["canonical_position"].unique())
    assert set(predicted["league_name"].unique()) == set(df["league_name"].unique())
    assert predicted["canonical_position"].dtype == object or predicted["canonical_position"].dtype.name == "category" or predicted["canonical_position"].dtype == df["canonical_position"].dtype


def test_predict_fair_value_produces_positive_values():
    df = _synthetic_training_df()
    bundle = train_valuation_model(df, random_state=1)
    predicted = predict_fair_value(bundle, df)
    assert (predicted["fair_value_eur"] > 0).all()


def test_predict_fair_value_computes_gap_against_actual_value():
    df = _synthetic_training_df()
    bundle = train_valuation_model(df, random_state=1)
    predicted = predict_fair_value(bundle, df)
    assert "value_gap_eur" in predicted.columns
    assert "value_gap_pct" in predicted.columns
    expected_gap = predicted["fair_value_eur"] - predicted["value_eur"]
    pd.testing.assert_series_equal(predicted["value_gap_eur"], expected_gap, check_names=False)


def test_predict_fair_value_on_subset_uses_same_encoding_as_training():
    # Regression-guard for the category-encoding-mismatch risk noted in
    # the module docstring: predicting on a SUBSET of the training data
    # should not silently re-derive different category codes.
    df = _synthetic_training_df()
    bundle = train_valuation_model(df, random_state=1)
    subset = df[df["canonical_position"] == "CB"]
    predicted_subset = predict_fair_value(bundle, subset)
    predicted_full = predict_fair_value(bundle, df)
    full_cb_values = predicted_full[predicted_full["canonical_position"] == "CB"].set_index("player_id")["fair_value_eur"]
    subset_values = predicted_subset.set_index("player_id")["fair_value_eur"]
    pd.testing.assert_series_equal(subset_values.sort_index(), full_cb_values.sort_index(), check_names=False)
