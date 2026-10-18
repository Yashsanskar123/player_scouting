import json

import pandas as pd
import pytest

from src.features.replacement_finder import find_replacements


def _df():
    rows = [
        {"player_id": "outgoing", "season": 2425, "short_name": "Outgoing CB", "canonical_position": "CB",
         "broad_position_group": "Defender", "value_eur": 40_000_000, "age_fifa": 29, "performance_score": 70,
         "development_potential": 68, "sample_reliability_score": 80,
         "recruitment_risk_tier": "LOW",
         "per_90_minutes_tackles_tkl_pctile": 70, "physic": 75, "pace": 60, "height_cm": 188, "weight_kg": 82,
         "component_defending": 75, "component_passing": 60, "component_progression": 55},
    ]
    # A cheaper, younger, similar CB -- should be flagged with clear advantages.
    rows.append({
        "player_id": "cheap_young", "season": 2425, "short_name": "Cheap Young CB", "canonical_position": "CB",
        "broad_position_group": "Defender", "value_eur": 10_000_000, "age_fifa": 22, "performance_score": 76,
        "development_potential": 80, "sample_reliability_score": 82,
        "recruitment_risk_tier": "LOW",
        "per_90_minutes_tackles_tkl_pctile": 70, "physic": 75, "pace": 60, "height_cm": 188, "weight_kg": 82,
        "component_defending": 75, "component_passing": 60, "component_progression": 55,
    })
    # An expensive, older CB -- worse value, no reason to be the "best value alternative".
    rows.append({
        "player_id": "expensive_old", "season": 2425, "short_name": "Expensive Old CB", "canonical_position": "CB",
        "broad_position_group": "Defender", "value_eur": 60_000_000, "age_fifa": 32, "performance_score": 65,
        "development_potential": 55, "sample_reliability_score": 70,
        "recruitment_risk_tier": "MEDIUM",
        "per_90_minutes_tackles_tkl_pctile": 68, "physic": 70, "pace": 55, "height_cm": 186, "weight_kg": 84,
        "component_defending": 70, "component_passing": 55, "component_progression": 50,
    })
    # A striker -- should never appear as a CB replacement candidate.
    rows.append({
        "player_id": "wrong_position", "season": 2425, "short_name": "A Striker", "canonical_position": "ST",
        "broad_position_group": "Forward", "value_eur": 5_000_000, "age_fifa": 22, "performance_score": 80,
        "development_potential": 85, "sample_reliability_score": 85,
        "recruitment_risk_tier": "LOW",
        "per_90_minutes_tackles_tkl_pctile": 10, "physic": 70, "pace": 85, "height_cm": 180, "weight_kg": 75,
        "component_defending": 10, "component_passing": 40, "component_progression": 40,
    })
    return pd.DataFrame(rows)


def test_replacement_search_excludes_wrong_position():
    result = find_replacements(_df(), outgoing_player_id="outgoing")
    candidate_ids = {c["player_id"] for c in result["candidates"]}
    assert "wrong_position" not in candidate_ids


def test_replacement_search_excludes_outgoing_player_from_own_results():
    result = find_replacements(_df(), outgoing_player_id="outgoing")
    candidate_ids = {c["player_id"] for c in result["candidates"]}
    assert "outgoing" not in candidate_ids


def test_budget_constraint_excludes_too_expensive_candidates():
    result = find_replacements(_df(), outgoing_player_id="outgoing", budget_eur=15_000_000)
    candidate_ids = {c["player_id"] for c in result["candidates"]}
    assert "expensive_old" not in candidate_ids
    assert "cheap_young" in candidate_ids


def test_age_constraint_filters_correctly():
    result = find_replacements(_df(), outgoing_player_id="outgoing", max_age=25)
    candidate_ids = {c["player_id"] for c in result["candidates"]}
    assert "expensive_old" not in candidate_ids  # age 32, excluded


def test_cheaper_candidate_gets_advantage_note():
    result = find_replacements(_df(), outgoing_player_id="outgoing")
    cheap = next(c for c in result["candidates"] if c["player_id"] == "cheap_young")
    assert any("cheaper" in a for a in cheap["advantages"])
    assert any("younger" in a for a in cheap["advantages"])


def test_best_value_alternative_is_the_cheapest_decent_fit():
    result = find_replacements(_df(), outgoing_player_id="outgoing")
    assert result["best_value_alternative_player_id"] == "cheap_young"


def test_unknown_outgoing_player_raises():
    try:
        find_replacements(_df(), outgoing_player_id="does-not-exist")
        assert False, "should have raised"
    except ValueError:
        pass


def test_no_candidates_matching_constraints_returns_empty_not_crash():
    result = find_replacements(_df(), outgoing_player_id="outgoing", budget_eur=100)  # impossible budget
    assert result["candidates"] == []
    assert "note" in result


def test_result_is_json_serializable():
    result = find_replacements(_df(), outgoing_player_id="outgoing")
    json.dumps(result)  # must not raise on numpy scalar types


def test_invalid_top_n_and_age_range_raise():
    with pytest.raises(ValueError, match="top_n must be at least 1"):
        find_replacements(_df(), outgoing_player_id="outgoing", top_n=0)

    with pytest.raises(ValueError, match="min_age cannot be greater"):
        find_replacements(
            _df(),
            outgoing_player_id="outgoing",
            min_age=30,
            max_age=20,
        )


def test_pool_size_and_scenarios_cover_full_qualifying_pool():
    result = find_replacements(
        _df(),
        outgoing_player_id="outgoing",
        top_n=1,
    )

    assert result["candidate_pool_size"] == 2
    assert len(result["candidates"]) == 1
    assert result["outgoing_player"]["broad_position_group"] == "Defender"

    scenario_keys = {scenario["key"] for scenario in result["scenarios"]}
    assert {
        "like_for_like",
        "succession",
        "value",
        "upside",
        "evidence",
    }.issubset(scenario_keys)


def test_latest_outgoing_season_is_used():
    frame = _df()
    latest = frame.iloc[0].copy()
    latest["season"] = 2526
    latest["value_eur"] = 55_000_000
    frame = pd.concat([frame, pd.DataFrame([latest])], ignore_index=True)

    result = find_replacements(frame, outgoing_player_id="outgoing")

    assert result["outgoing_player"]["value_eur"] == 55_000_000


def test_empty_pool_includes_complete_response_metadata():
    result = find_replacements(
        _df(),
        outgoing_player_id="outgoing",
        budget_eur=100,
    )

    assert result["candidate_pool_size"] == 0
    assert result["scenarios"] == []
    assert result["constraints"]["budget_eur"] == 100
    assert result["methodology"]["fit_weights"]["tactical"] == 0.35
