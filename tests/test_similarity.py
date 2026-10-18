import pandas as pd

from src.features.similarity_v2 import find_similar_players_multifacet


def _df():
    rows = [
        {"player_id": "st1", "short_name": "Target Striker", "canonical_position": "ST",
         "broad_position_group": "Forward", "pace": 85, "physic": 75, "height_cm": 182, "weight_kg": 78,
         "value_eur": 50_000_000, "wage_eur": 200_000, "age_fifa": 25,
         "component_attacking": 85, "component_chance_creation": 60, "component_passing": 50,
         "component_progression": 55, "component_defending": 20,
         "per_90_minutes_gls_pctile": 90, "per_90_minutes_ast_pctile": 60, "per_90_minutes_prg_c_pctile": 55,
         "per_90_minutes_prg_p_pctile": 50, "per_90_minutes_tackles_tkl_pctile": 20, "per_90_minutes_int_pctile": 20,
         "total_cmppct_pctile": 60, "per_90_minutes_kp_pctile": 55, "sca_sca90_pctile": 60},
        {"player_id": "st2", "short_name": "Similar Striker", "canonical_position": "ST",
         "broad_position_group": "Forward", "pace": 86, "physic": 74, "height_cm": 183, "weight_kg": 79,
         "value_eur": 48_000_000, "wage_eur": 190_000, "age_fifa": 24,
         "component_attacking": 84, "component_chance_creation": 58, "component_passing": 49,
         "component_progression": 54, "component_defending": 22,
         "per_90_minutes_gls_pctile": 88, "per_90_minutes_ast_pctile": 58, "per_90_minutes_prg_c_pctile": 53,
         "per_90_minutes_prg_p_pctile": 49, "per_90_minutes_tackles_tkl_pctile": 22, "per_90_minutes_int_pctile": 21,
         "total_cmppct_pctile": 58, "per_90_minutes_kp_pctile": 54, "sca_sca90_pctile": 58},
        {"player_id": "cb1", "short_name": "Different Centre Back", "canonical_position": "CB",
         "broad_position_group": "Defender", "pace": 65, "physic": 85, "height_cm": 190, "weight_kg": 88,
         "value_eur": 30_000_000, "wage_eur": 120_000, "age_fifa": 27,
         "component_attacking": 10, "component_chance_creation": 15, "component_passing": 60,
         "component_progression": 40, "component_defending": 85,
         "per_90_minutes_gls_pctile": 5, "per_90_minutes_ast_pctile": 10, "per_90_minutes_prg_c_pctile": 30,
         "per_90_minutes_prg_p_pctile": 40, "per_90_minutes_tackles_tkl_pctile": 85, "per_90_minutes_int_pctile": 88,
         "total_cmppct_pctile": 70, "per_90_minutes_kp_pctile": 15, "sca_sca90_pctile": 10},
    ]
    return pd.DataFrame(rows)


def test_similarity_excludes_target_player_from_results():
    result = find_similar_players_multifacet(_df(), player_id="st1", top_n=10)
    assert "st1" not in set(result["player_id"])


def test_position_restriction_excludes_different_broad_position_group():
    # Regression test: an earlier version compared across all positions
    # and could rank a CB as a striker's "most similar player" purely on
    # incidental feature closeness. Default restricts to same broad
    # position group.
    result = find_similar_players_multifacet(_df(), player_id="st1", top_n=10)
    assert "cb1" not in set(result["player_id"])
    assert "st2" in set(result["player_id"])


def test_position_restriction_can_be_disabled():
    result = find_similar_players_multifacet(
        _df(), player_id="st1", top_n=10, restrict_to_broad_position_group=False
    )
    assert "cb1" in set(result["player_id"])


def test_similar_player_scores_higher_than_dissimilar_player():
    result = find_similar_players_multifacet(
        _df(), player_id="st1", top_n=10, restrict_to_broad_position_group=False
    )
    st2_score = result.loc[result["player_id"] == "st2", "overall_similarity"].iloc[0]
    cb1_score = result.loc[result["player_id"] == "cb1", "overall_similarity"].iloc[0]
    assert st2_score > cb1_score


def test_all_facets_present_in_output():
    result = find_similar_players_multifacet(_df(), player_id="st1", top_n=10)
    for facet in ["statistical_similarity", "physical_similarity", "tactical_similarity", "market_similarity"]:
        assert facet in result.columns


def test_unknown_player_id_raises():
    try:
        find_similar_players_multifacet(_df(), player_id="does-not-exist")
        assert False, "should have raised"
    except ValueError:
        pass


def test_missing_player_id_column_raises():
    df = _df().drop(columns=["player_id"])
    try:
        find_similar_players_multifacet(df, player_id="st1")
        assert False, "should have raised"
    except ValueError:
        pass


def test_similarity_scores_bounded_0_100():
    result = find_similar_players_multifacet(
        _df(), player_id="st1", top_n=10, restrict_to_broad_position_group=False
    )
    for facet in ["statistical_similarity", "physical_similarity", "tactical_similarity", "market_similarity", "overall_similarity"]:
        valid = result[facet].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()
