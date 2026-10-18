import pandas as pd

from src.features.profile_intelligence import (
    build_profile_intelligence,
)


def test_profile_intelligence_is_cutoff_aware_and_windowed():
    df = pd.DataFrame([
        {
            "player_id": "p1",
            "season": 2021,
            "performance_score": 50,
            "playing_time_min": 1000,
            "age_fifa": 20,
            "canonical_position": "CM",
            "club_name": "A",
            "league_name": "L",
            "development_potential": 70,
        },
        {
            "player_id": "p1",
            "season": 2022,
            "performance_score": 60,
            "playing_time_min": 1100,
            "age_fifa": 21,
            "canonical_position": "CM",
            "club_name": "A",
            "league_name": "L",
            "development_potential": 75,
        },
        {
            "player_id": "p1",
            "season": 2023,
            "performance_score": 70,
            "playing_time_min": 1200,
            "age_fifa": 22,
            "canonical_position": "CAM",
            "club_name": "B",
            "league_name": "L2",
            "development_potential": 82,
        },
        {
            "player_id": "p1",
            "season": 2024,
            "performance_score": 80,
            "playing_time_min": 1300,
            "age_fifa": 23,
            "canonical_position": "CAM",
            "club_name": "B",
            "league_name": "L2",
            "development_potential": 85,
        },
        {
            "player_id": "p1",
            "season": 2025,
            "performance_score": 90,
            "playing_time_min": 1400,
            "age_fifa": 24,
            "canonical_position": "ST",
            "club_name": "C",
            "league_name": "L3",
            "development_potential": 88,
        },
    ])

    out = build_profile_intelligence(
        df,
        "p1",
        2024,
    )

    assert out["available"] is True

    assert (
        out["windows"]["three_year"]["average_performance"]
        == 70.0
    )

    assert out["peak"]["season"] == 2024

    assert (
        out["selected_season"]["season"]
        == 2024
    )

    assert (
        out["role_evolution"]["changes"]
        == 1
    )

    assert 2025 not in [
        x["season"]
        for x in out["trajectory"]
    ]


def test_profile_intelligence_uses_minutes_for_trend():
    df = pd.DataFrame([
        {
            "player_id": "p1",
            "season": 2021,
            "performance_score": 40,
            "playing_time_min": 300,
        },
        {
            "player_id": "p1",
            "season": 2022,
            "performance_score": 50,
            "playing_time_min": 1000,
        },
        {
            "player_id": "p1",
            "season": 2023,
            "performance_score": 60,
            "playing_time_min": 1100,
        },
    ])

    out = build_profile_intelligence(
        df,
        "p1",
        2023,
    )

    assert (
        out["trend"]["eligible_seasons"]
        == 2
    )

    assert abs(
        out["trend"]["performance_slope_per_season"]
        - 10.0
    ) < 1e-9