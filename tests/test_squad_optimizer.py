import pandas as pd

from src.optimization.squad_optimizer import (
    optimize_squad_ilp,
    simulate_transfer,
    FORMATIONS,
)


def _candidate_pool():
    rows = []

    # 3 GK, 4 CB, 3 LB, 3 RB, 3 CM, 3 CDM,
    # 3 LW, 3 RW, 3 ST -- enough for a 4-3-3
    specs = {
        "GK": 3,
        "CB": 4,
        "LB": 3,
        "RB": 3,
        "CM": 3,
        "CDM": 3,
        "LW": 3,
        "RW": 3,
        "ST": 3,
    }

    i = 0

    for pos, n in specs.items():
        for j in range(n):
            rows.append(
                {
                    "player_id": f"p{i}",
                    "short_name": f"{pos}-{j}",
                    "canonical_position": pos,
                    "performance_score": 50 + j * 10,
                    "value_eur": (
                        10_000_000
                        + j * 5_000_000
                    ),
                }
            )

            i += 1

    return pd.DataFrame(rows)


def test_optimizer_respects_formation_headcount():
    pool = _candidate_pool()

    result = optimize_squad_ilp(
        pool,
        formation="4-3-3",
        budget_eur=1_000_000_000,
    )

    assert result["status"] == "optimal"

    selected = pd.DataFrame(
        result["selected_players"]
    )

    counts = (
        selected["canonical_position"]
        .value_counts()
        .to_dict()
    )

    assert counts == FORMATIONS["4-3-3"]


def test_optimizer_respects_budget_constraint():
    pool = _candidate_pool()

    budget = 150_000_000

    result = optimize_squad_ilp(
        pool,
        formation="4-3-3",
        budget_eur=budget,
    )

    assert result["status"] == "optimal"

    assert (
        result["total_cost_eur"]
        <= budget + 1
    )


def test_optimizer_picks_best_affordable_quality_not_just_cheapest():
    pool = _candidate_pool()

    unconstrained = optimize_squad_ilp(
        pool,
        formation="4-3-3",
        budget_eur=None,
    )

    constrained = optimize_squad_ilp(
        pool,
        formation="4-3-3",
        budget_eur=150_000_000,
    )

    assert (
        unconstrained["projected_squad_quality"]
        >= constrained["projected_squad_quality"]
    )


def test_optimizer_infeasible_when_position_missing():
    pool = _candidate_pool()

    pool = pool[
        pool["canonical_position"] != "GK"
    ]

    result = optimize_squad_ilp(
        pool,
        formation="4-3-3",
        budget_eur=1_000_000_000,
    )

    assert result["status"] == "infeasible"


def test_optimizer_unknown_formation_raises():
    pool = _candidate_pool()

    try:
        optimize_squad_ilp(
            pool,
            formation="not-a-real-formation",
        )

        assert False, "should have raised"

    except ValueError:
        pass


# ---------------------------------------------------------
# simulate_transfer regression tests
# ---------------------------------------------------------


def test_simulate_transfer_swap_same_size():
    result = simulate_transfer(
        current_squad_quality=60.0,
        outgoing_quality=50.0,
        incoming_quality=70.0,
        squad_size_before=23,
        squad_size_after=23,
    )

    expected_after = (
        60.0 * 23
        - 50.0
        + 70.0
    ) / 23

    assert (
        abs(
            result["after_squad_rating"]
            - round(expected_after, 1)
        )
        < 0.05
    )


def test_simulate_transfer_pure_addition_uses_correct_denominator():
    result = simulate_transfer(
        current_squad_quality=60.0,
        outgoing_quality=0.0,
        incoming_quality=70.0,
        squad_size_before=23,
        squad_size_after=24,
    )

    assert (
        abs(
            result["after_squad_rating"]
            - 60.4
        )
        < 0.05
    )


def test_simulate_transfer_default_squad_size_after_matches_before():
    result = simulate_transfer(
        current_squad_quality=60.0,
        outgoing_quality=50.0,
        incoming_quality=70.0,
        squad_size_before=23,
    )

    expected_after = (
        60.0 * 23
        - 50.0
        + 70.0
    ) / 23

    assert (
        abs(
            result["after_squad_rating"]
            - round(expected_after, 1)
        )
        < 0.05
    )


def test_simulate_transfer_rejects_non_positive_squad_size():
    try:
        simulate_transfer(
            current_squad_quality=60.0,
            outgoing_quality=0.0,
            incoming_quality=70.0,
            squad_size_before=0,
        )

        assert False, "should have raised"

    except ValueError:
        pass


def test_optimizer_strategy_is_returned_and_changes_weights():
    pool = _candidate_pool()

    balanced = optimize_squad_ilp(
        pool,
        formation="4-3-3",
        budget_eur=1_000_000_000,
        strategy="balanced",
    )

    development = optimize_squad_ilp(
        pool,
        formation="4-3-3",
        budget_eur=1_000_000_000,
        strategy="development",
    )

    assert balanced["status"] == "optimal"
    assert development["status"] == "optimal"

    assert balanced["strategy"] == "balanced"
    assert development["strategy"] == "development"

    assert (
        balanced["strategy_weights"]
        != development["strategy_weights"]
    )


def test_optimizer_returns_richer_player_evidence():
    pool = _candidate_pool()

    pool["development_potential"] = (
        pool["performance_score"] + 10
    )

    pool["expected_performance_12m"] = (
        pool["performance_score"] + 5
    )

    pool["sample_reliability_score"] = 80

    pool["fair_value_eur"] = (
        pool["value_eur"] * 1.1
    )

    pool["value_gap_pct"] = 10

    pool["age_fifa"] = 24

    result = optimize_squad_ilp(
        pool,
        formation="4-3-3",
        budget_eur=1_000_000_000,
    )

    assert result["status"] == "optimal"

    assert (
        result["candidate_pool_size"]
        == len(pool)
    )

    assert (
        result["average_potential"]
        is not None
    )

    assert (
        result[
            "average_expected_performance_12m"
        ]
        is not None
    )

    assert (
        result["average_reliability"]
        is not None
    )

    assert result["selected_players"]

    assert (
        "development_potential"
        in result["selected_players"][0]
    )

    assert (
        "expected_performance_12m"
        in result["selected_players"][0]
    )

    assert (
        "sample_reliability_score"
        in result["selected_players"][0]
    )


def test_optimizer_rejects_unknown_strategy():
    pool = _candidate_pool()

    try:
        optimize_squad_ilp(
            pool,
            formation="4-3-3",
            strategy="not-a-real-strategy",
        )

        assert False, "should have raised"

    except ValueError:
        pass


def test_optimizer_rejects_negative_budget():
    pool = _candidate_pool()

    try:
        optimize_squad_ilp(
            pool,
            formation="4-3-3",
            budget_eur=-1,
        )

        assert False, "should have raised"

    except ValueError:
        pass