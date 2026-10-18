import pandas as pd

from src.identity.resolve_identity import assign_player_ids, duplicate_identity_report, build_player_identity_table


def test_same_player_gets_same_id_across_seasons(pipeline_df):
    steady_rows = pipeline_df[pipeline_df["short_name"] == "A. Steady"]
    assert len(steady_rows) == 3
    assert steady_rows["player_id"].nunique() == 1


def test_same_name_different_person_gets_different_id(pipeline_df):
    silva_rows = pipeline_df[pipeline_df["short_name"] == "A. Silva"]
    assert len(silva_rows) == 2
    assert silva_rows["player_id"].nunique() == 2, "different nationality/birth year must disambiguate"


def test_identity_confidence_flagged_correctly():
    df = pd.DataFrame([
        {"short_name": "X", "long_name": "X Full", "nationality_name": "England", "born_fifa": 1999},
        {"short_name": "Y", "long_name": "Y Full", "nationality_name": None, "born_fifa": None},
    ])
    result = assign_player_ids(df)
    assert result.loc[0, "identity_confidence"] == "high"
    assert result.loc[1, "identity_confidence"] == "low"


def test_duplicate_identity_report_shape(pipeline_df):
    report = duplicate_identity_report(pipeline_df)
    assert report["unique_player_ids"] == pipeline_df["player_id"].nunique()
    assert report["total_rows"] == len(pipeline_df)


def test_player_identity_table_one_row_per_player(pipeline_df):
    identity = build_player_identity_table(pipeline_df)
    assert len(identity) == pipeline_df["player_id"].nunique()
    assert identity["player_id"].is_unique


def test_player_identity_table_tracks_season_span(pipeline_df):
    identity = build_player_identity_table(pipeline_df)
    steady_id = pipeline_df.loc[pipeline_df["short_name"] == "A. Steady", "player_id"].iloc[0]
    row = identity[identity["player_id"] == steady_id].iloc[0]
    assert row["seasons_observed"] == 3
    assert row["first_season"] == 2223
    assert row["last_season"] == 2425
