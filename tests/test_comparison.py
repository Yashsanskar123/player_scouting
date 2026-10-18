import pandas as pd

from src.features.comparison import compare_players


def _df():
    return pd.DataFrame([
        {"player_id": "p1", "season": 2425, "short_name": "A", "canonical_position": "ST",
         "performance_score": 80, "age_fifa": 24, "value_eur": 50_000_000,
         "per_90_minutes_gls_pctile": 90, "per_90_minutes_x_g_pctile": 85},
        {"player_id": "p2", "season": 2425, "short_name": "B", "canonical_position": "ST",
         "performance_score": 60, "age_fifa": 28, "value_eur": 20_000_000,
         "per_90_minutes_gls_pctile": 50, "per_90_minutes_x_g_pctile": 55},
        {"player_id": "p3", "season": 2425, "short_name": "C", "canonical_position": "CB",
         "performance_score": 70, "age_fifa": 26, "value_eur": 15_000_000,
         "per_90_minutes_gls_pctile": None, "per_90_minutes_x_g_pctile": None},  # missing on purpose
    ])


def test_compare_returns_one_entry_per_player():
    result = compare_players(_df(), ["p1", "p2"])
    assert len(result["players"]) == 2
    assert {p["player_id"] for p in result["players"]} == {"p1", "p2"}


def test_compare_rejects_too_few_players():
    try:
        compare_players(_df(), ["p1"])
        assert False, "should have raised"
    except ValueError:
        pass


def test_compare_rejects_too_many_players():
    df = _df()
    try:
        compare_players(df, ["p1", "p2", "p3", "p1", "p2", "p3"])  # 6, over MAX_PLAYERS
        assert False, "should have raised"
    except ValueError:
        pass


def test_compare_rejects_unknown_player_id():
    try:
        compare_players(_df(), ["p1", "does-not-exist"])
        assert False, "should have raised"
    except ValueError:
        pass


def test_percentile_comparison_excludes_metrics_missing_for_any_player():
    # p3 has no per_90_minutes_gls_pctile at all -- comparing p1 vs p3
    # should NOT include that metric (no silently-blank cells).
    result = compare_players(_df(), ["p1", "p3"])
    metrics = {row["metric"] for row in result["percentile_comparison"]}
    assert "gls" not in metrics


def test_percentile_comparison_includes_metrics_present_for_all_selected():
    result = compare_players(_df(), ["p1", "p2"])
    metrics = {row["metric"] for row in result["percentile_comparison"]}
    assert "gls" in metrics
    row = next(r for r in result["percentile_comparison"] if r["metric"] == "gls")
    assert row["values"]["p1"] == 90
    assert row["values"]["p2"] == 50


def test_summary_values_are_json_safe_native_types():
    import json
    result = compare_players(_df(), ["p1", "p2"])
    json.dumps(result)  # must not raise on numpy scalar types
