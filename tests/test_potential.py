import pandas as pd

from src.features.potential import compute_potential, RECENCY_WEIGHT, MIN_SEASONS_FOR_BLEND


def test_recency_weight_matches_backtested_value():
    # Regression guard: RECENCY_WEIGHT=0.4 was found by grid search against
    # a real walk-forward backtest (src/validation/backtest_potential.py,
    # documented in docs/VALIDATION.md) to beat every alternative tested.
    # If someone changes this constant, they should have re-run that
    # backtest and updated the docs -- this test just makes the dependency
    # visible rather than letting the constant drift silently.
    assert RECENCY_WEIGHT == 0.4


def test_multi_season_player_uses_recency_mean_blend():
    df = pd.DataFrame([
        {"player_id": "p1", "season": 2223, "performance_score": 60, "potential": 80, "age_fifa": 24},
        {"player_id": "p1", "season": 2324, "performance_score": 70, "potential": 80, "age_fifa": 25},
        {"player_id": "p1", "season": 2425, "performance_score": 80, "potential": 80, "age_fifa": 26},
    ])
    result = compute_potential(df)
    last_row = result[result["season"] == 2425].iloc[0]
    assert last_row["trend_source"] == "recency_mean_blend"
    expected = RECENCY_WEIGHT * 80 + (1 - RECENCY_WEIGHT) * ((60 + 70 + 80) / 3)
    assert abs(last_row["expected_performance_12m"] - round(expected, 1)) < 0.15


def test_single_season_player_uses_age_curve_fallback():
    df = pd.DataFrame([{"player_id": "p2", "season": 2425, "performance_score": 50, "potential": 85, "age_fifa": 19}])
    result = compute_potential(df)
    row = result.iloc[0]
    assert row["trend_source"] == "age_curve_prior"
    assert pd.notna(row["expected_performance_12m"])
    assert pd.notna(row["development_potential"])


def test_fifa_potential_exposed_unchanged_as_benchmark_not_truth():
    # Per spec: FIFA's potential rating must be exposed as a labeled
    # benchmark, never silently used as if it were validated truth.
    df = pd.DataFrame([{"player_id": "p3", "season": 2425, "performance_score": 50, "potential": 92, "age_fifa": 22}])
    result = compute_potential(df)
    assert result.iloc[0]["fifa_potential_benchmark"] == 92


def test_development_potential_bounded_0_100():
    df = pd.DataFrame([
        {"player_id": "p4", "season": 2425, "performance_score": 99, "potential": 99, "age_fifa": 17},
        {"player_id": "p5", "season": 2425, "performance_score": 1, "potential": 1, "age_fifa": 38},
    ])
    result = compute_potential(df)
    valid = result["development_potential"].dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_missing_player_id_or_season_does_not_crash():
    df = pd.DataFrame([{"performance_score": 60, "potential": 70, "age_fifa": 25}])
    result = compute_potential(df)
    assert "fifa_potential_benchmark" in result.columns
