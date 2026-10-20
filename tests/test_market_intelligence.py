import json

import pandas as pd
import pytest

from src.features.market_intelligence import (
    build_market_intelligence,
)


def _df():

    return pd.DataFrame([
        {
            "player_id": "a",
            "short_name": "High Value",
            "canonical_position": "CM",
            "club_name": "Club A",
            "league_name": "League A",
            "age_fifa": 22,
            "value_eur": 10_000_000,
            "fair_value_eur": 14_000_000,
            "value_gap_pct": 40,
            "performance_score": 78,
            "development_potential": 82,
            "expected_performance_12m": 80,
            "playing_time_min": 2000,
            "recruitment_risk_tier": "LOW",
            "recruitment_risk_score": 15,
            "sample_reliability_score": 85,
            "wage_eur": 300_000,
        },
        {
            "player_id": "b",
            "short_name": "Efficient CB",
            "canonical_position": "CB",
            "club_name": "Club B",
            "league_name": "League B",
            "age_fifa": 27,
            "value_eur": 20_000_000,
            "fair_value_eur": 23_000_000,
            "value_gap_pct": 15,
            "performance_score": 82,
            "development_potential": 65,
            "expected_performance_12m": 79,
            "playing_time_min": 2500,
            "recruitment_risk_tier": "MEDIUM",
            "recruitment_risk_score": 30,
            "sample_reliability_score": 90,
            "wage_eur": 500_000,
        },
        {
            "player_id": "c",
            "short_name": "Weak Gap",
            "canonical_position": "ST",
            "club_name": "Club C",
            "league_name": "League A",
            "age_fifa": 24,
            "value_eur": 30_000_000,
            "fair_value_eur": 31_000_000,
            "value_gap_pct": 3,
            "performance_score": 55,
            "development_potential": 80,
            "expected_performance_12m": 60,
            "playing_time_min": 1000,
            "recruitment_risk_tier": "LOW",
            "recruitment_risk_score": 10,
            "sample_reliability_score": 60,
            "wage_eur": 900_000,
        },
    ])


def test_base_pool_and_segments():

    result = build_market_intelligence(
        _df(),
        top_n=10,
    )

    assert result["total"] == 2

    assert (
        result["summary"]
        ["high_potential_count"]
        == 1
    )

    assert (
        result["summary"]
        ["high_performance_count"]
        == 2
    )

    assert (
        result["summary"]
        ["low_risk_count"]
        == 1
    )


def test_default_discovery_pool_does_not_require_positive_value_gap():
    df = _df()
    df.loc[df["player_id"] == "c", "performance_score"] = 70
    df.loc[df["player_id"] == "c", "value_gap_pct"] = -15

    result = build_market_intelligence(df)

    assert result["total"] == 3
    assert "c" in {row["player_id"] for row in result["results"]}


def test_performance_segment_does_not_require_positive_value_gap():
    df = _df()
    df.loc[df["player_id"] == "c", "performance_score"] = 80
    df.loc[df["player_id"] == "c", "value_gap_pct"] = -15

    result = build_market_intelligence(df, segment="performance")

    assert result["selected_total"] == 3
    assert "c" in {row["player_id"] for row in result["results"]}


def test_default_discovery_pool_does_not_require_positive_fair_value_gap():
    df = _df()
    df.loc[df.player_id == "b", "value_gap_pct"] = -35
    df.loc[df.player_id == "b", "fair_value_eur"] = 13_000_000
    result = build_market_intelligence(df, min_performance_score=60)
    ids = {row["player_id"] for row in result["results"]}
    assert "b" in ids
    assert (
        "failed fair-value gap signal is not part of the score"
        in result["methodology"]["opportunity_score"]
    )


def test_value_segment_remains_explicitly_gap_based():
    result = build_market_intelligence(_df(), segment="value")
    assert all(
        (row.get("value_gap_pct") or 0) >= 20
        for row in result["results"]
    )


def test_filters():

    result = build_market_intelligence(
        _df(),
        canonical_position="CB",
    )

    assert result["total"] == 1

    assert (
        result["results"][0]["player_id"]
        == "b"
    )


def test_segment_selection():

    result = build_market_intelligence(
        _df(),
        segment="upside",
    )

    assert result["selected_total"] == 1

    assert (
        result["results"][0]["player_id"]
        == "a"
    )


def test_opportunity_score_is_present():

    result = build_market_intelligence(
        _df()
    )

    assert (
        result["results"][0]
        ["opportunity_score"]
        is not None
    )


def test_invalid_inputs():

    with pytest.raises(ValueError):

        build_market_intelligence(
            _df(),
            min_age=30,
            max_age=20,
        )

    with pytest.raises(ValueError):

        build_market_intelligence(
            _df(),
            segment="unknown",
        )

    with pytest.raises(ValueError):

        build_market_intelligence(
            _df(),
            top_n=0,
        )


def test_json_serializable():

    json.dumps(
        build_market_intelligence(
            _df()
        )
    )

def test_min_reliability_tier_filters_small_samples():
    df = _df()
    df["sample_reliability_tier"] = ["High", "Low", "Very Low", "Moderate"][: len(df)] + ["High"] * max(0, len(df) - 4)
    df = df.iloc[: len(df)].copy()

    everything = build_market_intelligence(df, min_performance_score=0, min_value_gap_pct=-100)
    high_only = build_market_intelligence(
        df, min_performance_score=0, min_value_gap_pct=-100, min_reliability_tier="High"
    )

    assert high_only["total"] <= everything["total"]
    assert all(
        r.get("player_id") in set(df[df["sample_reliability_tier"] == "High"]["player_id"])
        for r in high_only["results"]
    )


def test_min_reliability_tier_rejects_unknown_value():
    with pytest.raises(ValueError):
        build_market_intelligence(_df(), min_reliability_tier="Excellent")
