import pandas as pd

from src.features.risk import compute_risk, TOP_LEAGUES


def test_young_player_gets_age_risk():
    df = pd.DataFrame([
        {"age_fifa": 18, "playing_time_min": 2000, "playing_time_starts": 22, "playing_time_mp": 23,
         "league_name": "Premier League", "value_eur": 1_000_000},
        {"age_fifa": 25, "playing_time_min": 2000, "playing_time_starts": 22, "playing_time_mp": 23,
         "league_name": "Premier League", "value_eur": 1_000_000},
    ])
    result = compute_risk(df)
    assert result.loc[0, "age_risk"] > result.loc[1, "age_risk"]


def test_ageing_player_gets_age_risk_too():
    # age_risk is deliberately bimodal per docs/VALIDATION.md -- both very
    # young AND ageing players should score higher than a player in their
    # prime, not just young players.
    df = pd.DataFrame([
        {"age_fifa": 34, "playing_time_min": 2000, "playing_time_starts": 22, "playing_time_mp": 23,
         "league_name": "Premier League", "value_eur": 1_000_000},
        {"age_fifa": 25, "playing_time_min": 2000, "playing_time_starts": 22, "playing_time_mp": 23,
         "league_name": "Premier League", "value_eur": 1_000_000},
    ])
    result = compute_risk(df)
    assert result.loc[0, "age_risk"] > result.loc[1, "age_risk"]


def test_low_minutes_increases_availability_risk():
    df = pd.DataFrame([
        {"age_fifa": 25, "sample_reliability_score": 20.0, "league_name": "Premier League", "value_eur": 1_000_000},
        {"age_fifa": 25, "sample_reliability_score": 95.0, "league_name": "Premier League", "value_eur": 1_000_000},
    ])
    result = compute_risk(df)
    assert result.loc[0, "availability_risk"] > result.loc[1, "availability_risk"]


def test_outside_top_league_increases_league_transition_risk():
    df = pd.DataFrame([
        {"age_fifa": 25, "playing_time_min": 2000, "playing_time_starts": 22, "playing_time_mp": 23,
         "league_name": "Eredivisie", "value_eur": 1_000_000},
        {"age_fifa": 25, "playing_time_min": 2000, "playing_time_starts": 22, "playing_time_mp": 23,
         "league_name": "Premier League", "value_eur": 1_000_000},
    ])
    result = compute_risk(df)
    assert result.loc[0, "league_transition_risk"] > result.loc[1, "league_transition_risk"]
    assert "Premier League" in TOP_LEAGUES


def test_risk_tier_is_ordered_categorical():
    df = pd.DataFrame([
        {"age_fifa": 19, "playing_time_min": 200, "playing_time_starts": 2, "playing_time_mp": 3,
         "league_name": "Eredivisie", "value_eur": 1_000_000},
        {"age_fifa": 26, "playing_time_min": 2900, "playing_time_starts": 32, "playing_time_mp": 33,
         "league_name": "Premier League", "value_eur": 1_000_000},
    ])
    result = compute_risk(df)
    assert result.loc[0, "recruitment_risk_tier"] in ("LOW", "MEDIUM", "HIGH")
    assert result.loc[1, "recruitment_risk_tier"] == "LOW"


def test_data_reliability_risk_reflects_missingness():
    df = pd.DataFrame([
        {"age_fifa": 25, "playing_time_min": 2000, "playing_time_starts": 22, "playing_time_mp": 23,
         "league_name": "Premier League", "value_eur": 1_000_000,
         "per_90_minutes_gls": 0.3, "per_90_minutes_ast": 0.1, "per_90_minutes_prg_c": 0.5,
         "per_90_minutes_tackles_tkl": 0.2},
        {"age_fifa": 25, "playing_time_min": 2000, "playing_time_starts": 22, "playing_time_mp": 23,
         "league_name": "Premier League", "value_eur": None,
         "per_90_minutes_gls": None, "per_90_minutes_ast": None, "per_90_minutes_prg_c": None,
         "per_90_minutes_tackles_tkl": None},
    ])
    result = compute_risk(df)
    assert result.loc[1, "data_reliability_risk"] > result.loc[0, "data_reliability_risk"]
