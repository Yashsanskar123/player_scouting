import pandas as pd

from src.features.percentiles import compute_percentiles, MIN_MINUTES_FOR_PEER_GROUP


def test_percentiles_computed_within_position_group(pipeline_df):
    # The CB with the highest tackles/90 among CBs should have a high
    # percentile on that metric relative to other CBs specifically.
    cbs = pipeline_df[pipeline_df["canonical_position"] == "CB"]
    best_tackler = cbs.loc[cbs["per_90_minutes_tackles_tkl"].idxmax()]
    assert best_tackler["per_90_minutes_tackles_tkl_pctile"] >= 80


def test_low_minutes_player_still_scored_but_excluded_as_peer():
    # C. Bench (180 minutes) has a very high raw tackle rate but should
    # not distort the percentile distribution for eligible (900+ minute)
    # peers -- it should still receive a percentile score itself, though.
    df = pd.DataFrame([
        {"canonical_position": "CB", "season": 2425, "playing_time_min": 180, "per_90_minutes_tackles_tkl": 5.0},
        *[
            {"canonical_position": "CB", "season": 2425, "playing_time_min": 2000, "per_90_minutes_tackles_tkl": v}
            for v in [0.2, 0.3, 0.4, 0.5, 0.6]
        ],
    ])
    result = compute_percentiles(df, metrics=["per_90_minutes_tackles_tkl"])
    low_minutes_row = result.iloc[0]
    assert pd.notna(low_minutes_row["per_90_minutes_tackles_tkl_pctile"]), "low-minute player should still get a percentile score"
    assert low_minutes_row["per_90_minutes_tackles_tkl_pctile"] == 100.0, "scored against the eligible peer distribution, not excluded from scoring entirely"


def test_peer_group_too_small_produces_no_percentile():
    # Fewer than 5 eligible peers -> no percentile computed for that group (too noisy to be meaningful).
    df = pd.DataFrame([
        {"canonical_position": "CB", "season": 2425, "playing_time_min": 2000, "per_90_minutes_tackles_tkl": v}
        for v in [0.2, 0.3, 0.4]
    ])
    result = compute_percentiles(df, metrics=["per_90_minutes_tackles_tkl"])
    assert result["per_90_minutes_tackles_tkl_pctile"].isna().all()


def test_different_seasons_are_separate_peer_groups():
    # A player shouldn't be compared against a different season's talent pool.
    df = pd.DataFrame([
        {"canonical_position": "CB", "season": 2223, "playing_time_min": 2000, "per_90_minutes_tackles_tkl": v}
        for v in [0.1, 0.2, 0.3, 0.4, 0.5]
    ] + [
        {"canonical_position": "CB", "season": 2425, "playing_time_min": 2000, "per_90_minutes_tackles_tkl": v}
        for v in [10.0, 20.0, 30.0, 40.0, 50.0]  # wildly different scale, different season
    ])
    result = compute_percentiles(df, metrics=["per_90_minutes_tackles_tkl"])
    # the lowest value in the 2223 group (0.1) and lowest in 2425 (10.0)
    # should both be low percentiles WITHIN their own season, not skewed
    # by the other season's completely different scale.
    season_2223 = result[result["season"] == 2223]
    assert season_2223["per_90_minutes_tackles_tkl_pctile"].min() < 25
    assert season_2223["per_90_minutes_tackles_tkl_pctile"].max() == 100
