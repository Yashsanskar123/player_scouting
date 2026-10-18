import pandas as pd

from src.taxonomy.positions import assign_position_taxonomy, POSITION_ALIASES, BROAD_GROUP


def test_canonical_position_from_primary_listed_position():
    df = pd.DataFrame([{"player_positions": "ST, CF", "pos": "FW"}])
    result = assign_position_taxonomy(df)
    assert result.loc[0, "canonical_position"] == "ST"


def test_secondary_positions_captured():
    df = pd.DataFrame([{"player_positions": "CDM, CM", "pos": "MF"}])
    result = assign_position_taxonomy(df)
    assert result.loc[0, "secondary_positions"] == "CM"


def test_lm_rm_folded_into_cm_bucket():
    # LM/RM aren't in the canonical taxonomy list; they fold into CM
    # per POSITION_ALIASES rather than becoming an unmapped stray value.
    df = pd.DataFrame([{"player_positions": "LM", "pos": "MF"}])
    result = assign_position_taxonomy(df)
    assert result.loc[0, "canonical_position"] == "CM"


def test_broad_group_mapping_consistent_with_canonical_position():
    df = pd.DataFrame([
        {"player_positions": "CB", "pos": "DF"},
        {"player_positions": "ST", "pos": "FW"},
        {"player_positions": "GK", "pos": "GK"},
    ])
    result = assign_position_taxonomy(df)
    assert list(result["broad_position_group"]) == ["Defender", "Forward", "Goalkeeper"]


def test_position_conflict_flagged_when_fifa_and_fbref_disagree():
    # FIFA says CB (Defender) but FBref says FW -- a real conflict, should be flagged.
    df = pd.DataFrame([{"player_positions": "CB", "pos": "FW"}])
    result = assign_position_taxonomy(df)
    assert result.loc[0, "position_data_conflict"] == True  # noqa: E712


def test_no_conflict_flagged_when_they_agree():
    df = pd.DataFrame([{"player_positions": "CB", "pos": "DF"}])
    result = assign_position_taxonomy(df)
    assert result.loc[0, "position_data_conflict"] == False  # noqa: E712


def test_versatility_score_counts_distinct_canonical_positions():
    # LB and LWB are distinct canonical positions -> versatility 2, not 1.
    df = pd.DataFrame([{"player_positions": "LB, LWB", "pos": "DF"}])
    result = assign_position_taxonomy(df)
    assert result.loc[0, "positional_versatility_score"] == 2


def test_missing_position_data_does_not_crash():
    df = pd.DataFrame([{"player_positions": None, "pos": None}])
    result = assign_position_taxonomy(df)
    assert pd.isna(result.loc[0, "canonical_position"])
