import pandas as pd

from src.features.league_adjustment import build_league_transitions, fit_league_strength, apply_league_adjustment


def _synthetic_transitions_df():
    """Two players who each moved league_A -> league_B between seasons,
    with a consistent +10 performance jump -- a clean signal to recover.
    Plus enough same-league players to keep min_transitions checks happy
    for other tests, and a player who never changed league (no transition).
    """
    rows = []
    for i in range(12):
        rows.append({"player_id": f"mover_{i}", "season": 2223, "league_name": "League A", "performance_score": 50.0})
        rows.append({"player_id": f"mover_{i}", "season": 2324, "league_name": "League B", "performance_score": 60.0})
    rows.append({"player_id": "stayer", "season": 2223, "league_name": "League A", "performance_score": 55.0})
    rows.append({"player_id": "stayer", "season": 2324, "league_name": "League A", "performance_score": 55.0})
    return pd.DataFrame(rows)


def test_build_league_transitions_only_includes_actual_league_changes():
    result = build_league_transitions(_synthetic_transitions_df())
    assert len(result) == 12  # 12 movers, 1 stayer excluded
    assert (result["from_league"] == "League A").all()
    assert (result["to_league"] == "League B").all()
    assert (result["performance_delta"] == 10.0).all()


def test_fit_league_strength_recovers_consistent_signal():
    result = fit_league_strength(_synthetic_transitions_df(), min_transitions=5)
    assert result["n_transitions"] == 12
    # League B should come out ~10 points stronger than League A (anchor),
    # since every observed transition showed exactly a +10 jump.
    strengths = result["strengths"]
    diff = strengths["League B"] - strengths["League A"]
    assert abs(diff - 10.0) < 0.5


def test_fit_league_strength_anchors_most_observed_league_at_zero():
    result = fit_league_strength(_synthetic_transitions_df(), min_transitions=5)
    anchor = result["anchor_league"]
    assert result["strengths"][anchor] == 0.0


def test_leagues_below_min_transitions_excluded_not_crashed():
    df = _synthetic_transitions_df()
    result = fit_league_strength(df, min_transitions=100)  # nothing clears this bar
    assert result["strengths"] == {}
    assert set(result["insufficient_data_leagues"]) == {"League A", "League B"}


def test_empty_dataframe_does_not_crash():
    df = pd.DataFrame(columns=["player_id", "season", "league_name", "performance_score"])
    result = fit_league_strength(df)
    assert result["n_transitions"] == 0
    assert result["strengths"] == {}


def test_apply_league_adjustment_subtracts_strength_from_performance():
    df = pd.DataFrame([
        {"league_name": "League A", "performance_score": 60.0},
        {"league_name": "League B", "performance_score": 60.0},
    ])
    strengths = {"League A": 0.0, "League B": 5.0}
    result = apply_league_adjustment(df, strengths)
    assert result.loc[0, "adjusted_performance_score"] == 60.0
    assert result.loc[1, "adjusted_performance_score"] == 55.0  # discounted by the stat-inflating league's strength


def test_apply_league_adjustment_unknown_league_defaults_to_no_adjustment():
    df = pd.DataFrame([{"league_name": "Unmapped League", "performance_score": 60.0}])
    result = apply_league_adjustment(df, {"League A": 5.0})
    assert result.loc[0, "adjusted_performance_score"] == 60.0


def test_adjustment_bounded_0_100():
    df = pd.DataFrame([{"league_name": "League A", "performance_score": 98.0}])
    result = apply_league_adjustment(df, {"League A": -10.0})  # would push above 100 without clipping
    assert result.loc[0, "adjusted_performance_score"] <= 100
