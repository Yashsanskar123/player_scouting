import pandas as pd
from src.features.advanced_potential import compute_advanced_potential, backtest_advanced_horizons


def test_advanced_profile_separates_validated_12m_from_exploratory_horizons():
    df = pd.DataFrame([
        {"player_id":"p1","season":2021,"performance_score":60,"current_ability":60,"age_fifa":20,"fifa_potential_benchmark":85,"expected_performance_12m":65},
        {"player_id":"p1","season":2022,"performance_score":70,"current_ability":70,"age_fifa":21,"fifa_potential_benchmark":86,"expected_performance_12m":70},
        {"player_id":"p1","season":2023,"performance_score":78,"current_ability":78,"age_fifa":22,"fifa_potential_benchmark":87,"expected_performance_12m":75},
    ])
    out = compute_advanced_potential(df)
    row = out.iloc[-1]
    assert pd.notna(row.potential_12m)
    assert pd.notna(row.potential_24m)
    assert pd.notna(row.peak_projection)
    assert row.potential_projection_status in {"exploratory_empirical", "low_evidence", "exploratory"}


def test_empirical_probabilities_are_bounded():
    rows=[]
    for pid in range(40):
        rows += [
            {"player_id":str(pid),"season":2021,"performance_score":60,"age_fifa":21},
            {"player_id":str(pid),"season":2022,"performance_score":67,"age_fifa":22},
            {"player_id":str(pid),"season":2023,"performance_score":70,"age_fifa":23},
        ]
    out=compute_advanced_potential(pd.DataFrame(rows))
    row=out.iloc[-1]
    assert 0 <= row.breakout_probability <= 100
    assert 0 <= row.decline_probability <= 100
    assert row.potential_evidence_sample >= 30


def test_backtest_returns_horizon_metrics():
    rows=[]
    for pid in range(5):
        for season, score in [(2020,60),(2021,62),(2022,64),(2023,66),(2024,68)]:
            rows.append({"player_id":str(pid),"season":season,"performance_score":score})
    result=backtest_advanced_horizons(pd.DataFrame(rows), min_seasons=4)
    assert result["n"] > 0
    assert "1m_season" in result
    assert "2m_season" in result
