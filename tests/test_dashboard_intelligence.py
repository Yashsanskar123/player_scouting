import pandas as pd

from src.features.dashboard_intelligence import (
    TREND_MIN_MINUTES,
    breakout_candidates,
    canonical_player_season,
    season_movers,
    season_snapshot,
)


def _facts():
    return pd.DataFrame([
        {"player_id":"a","season":2324,"short_name":"A","canonical_position":"CM","club_name":"Old","age_fifa":22,"performance_score":60,"playing_time_min":1200,"development_potential":78,"value_eur":5_000_000},
        {"player_id":"a","season":2425,"short_name":"A","canonical_position":"CM","club_name":"New","age_fifa":23,"performance_score":72,"playing_time_min":1400,"development_potential":82,"value_eur":8_000_000},
        {"player_id":"b","season":2324,"short_name":"B","canonical_position":"ST","club_name":"Old","age_fifa":24,"performance_score":75,"playing_time_min":1500,"development_potential":72,"value_eur":10_000_000},
        {"player_id":"b","season":2425,"short_name":"B","canonical_position":"ST","club_name":"New","age_fifa":25,"performance_score":64,"playing_time_min":1600,"development_potential":70,"value_eur":9_000_000},
        {"player_id":"c","season":2425,"short_name":"C","canonical_position":"RW","club_name":"New","age_fifa":21,"performance_score":68,"playing_time_min":1300,"development_potential":86,"value_eur":4_000_000},
    ])


def test_canonical_player_season_deduplicates():
    df = _facts()
    duplicate = pd.concat([df, df.iloc[[0]].assign(performance_score=65)], ignore_index=True)
    out = canonical_player_season(duplicate[duplicate.season == 2324])
    assert len(out) == 2


def test_snapshot_uses_unique_players():
    result = season_snapshot(_facts(), 2425)
    assert result["player_count"] == 3
    assert result["average_performance"] is not None


def test_movers_require_minimum_minutes():
    result = season_movers(_facts(), 2425)
    assert result["previous_season"] == 2324
    assert any(r["player_id"] == "a" for r in result["improved"])
    assert any(r["player_id"] == "b" for r in result["declined"])
    assert result["method"]["min_minutes_each_season"] == TREND_MIN_MINUTES


def test_breakout_requires_youth_performance_potential_and_trend():
    result = breakout_candidates(_facts(), 2425)
    assert result["total"] == 1
    assert result["results"][0]["player_id"] == "a"
