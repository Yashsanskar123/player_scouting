import pandas as pd

from src.validation.market_signal_backtest import evaluate_market_signals
from src.validation.position_score_backtest import evaluate_position_scores


def _history():
    rows = []
    for player_index in range(12):
        for season_index, season in enumerate((2324, 2425, 2526)):
            performance = 40 + player_index * 3 + season_index
            rows.append({
                "player_id": f"p{player_index}",
                "season": season,
                "canonical_position": "GK" if player_index < 6 else "CB",
                "performance_score": performance,
                "playing_time_min": 900 + player_index * 100,
                "value_eur": 500_000 + player_index * 250_000,
                "age_fifa": 19 + player_index % 8 + season_index,
            })
    return pd.DataFrame(rows)


def test_market_signal_backtest_pairs_adjacent_seasons_and_returns_all_signals():
    result = evaluate_market_signals(_history())

    assert result["available"] is True
    assert result["n_pairs"] == 24
    assert {item["signal"] for item in result["results"]} == {
        "performance_baseline",
        "performance_value_efficiency",
        "age_adjusted_performance",
    }
    assert all("spearman_next_minutes" in item for item in result["results"])
    assert all("spearman_next_performance" in item for item in result["results"])


def test_market_signal_backtest_reports_missing_columns():
    result = evaluate_market_signals(pd.DataFrame({"player_id": ["p1"]}))
    assert result["available"] is False
    assert "value_eur" in result["reason"]


def test_position_score_backtest_reports_position_diagnostics():
    result = evaluate_position_scores(_history())

    assert result["available"] is True
    assert result["n_pairs"] == 24
    assert {item["position"] for item in result["positions"]} == {"GK", "CB"}
    assert all(item["available"] is False for item in result["positions"])


def test_position_score_backtest_handles_missing_required_columns():
    result = evaluate_position_scores(pd.DataFrame({"player_id": ["p1"]}))
    assert result["available"] is False
    assert "value_eur" in result["reason"]