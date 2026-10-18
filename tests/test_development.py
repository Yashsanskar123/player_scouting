import pandas as pd

from src.features.development_lab import build_development_lab


def sample():
    rows = []

    for season, perf, age in [
        (2223, 52, 21),
        (2324, 60, 22),
        (2425, 68, 23),
    ]:
        rows.append(
            {
                "player_id": "p1",
                "season": season,
                "short_name": "Test Player",
                "canonical_position": "CM",
                "club_name": "Club",
                "league_name": "League",
                "age_fifa": age,
                "performance_score": perf,
                "potential": 86,
                "fifa_potential_benchmark": 86,
                "expected_performance_12m": perf + 2,
                "playing_time_min": 1800,
                "sample_reliability_score": 82,
                "sample_reliability_tier": "HIGH",

                "per_90_minutes_prg_p_pctile": 30,
                "per_90_minutes_prg_c_pctile": 75,
                "total_cmppct_pctile": 82,
                "per_90_minutes_kp_pctile": 35,
                "per_90_minutes_tackles_tkl_pctile": 65,
            }
        )

    return pd.DataFrame(rows)


def test_development_lab_is_focused_and_longitudinal():
    result = build_development_lab(
        sample(),
        "p1",
        2425,
    )

    assert result["player"]["season"] == 2425

    assert len(result["trajectory"]) == 3

    assert result["outlook"]["current"] == 68

    assert result["development_priorities"]

    assert result["strengths_to_preserve"]


def test_unknown_player():
    try:
        build_development_lab(
            sample(),
            "missing",
            2425,
        )

        assert False

    except ValueError as exc:
        assert "No player found" in str(exc)