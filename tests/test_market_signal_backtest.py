import pandas as pd

from src.validation.market_signal_backtest import evaluate_market_signals


def test_backtest_pairs_adjacent_observed_seasons_and_reports_baseline():
    rows = []
    for player_index in range(50):
        for season in [2122, 2223, 2324]:
            minutes = 600 + player_index * 15 + (season - 2122) * 20
            rows.append({
                "player_id": f"p{player_index}",
                "season": season,
                "playing_time_min": minutes,
                "performance_score": 40 + player_index,
                "value_eur": 100_000 + player_index * 50_000,
                "age_fifa": 18 + player_index % 15,
                "canonical_position": "CB" if player_index % 2 else "ST",
            })

    result = evaluate_market_signals(pd.DataFrame(rows), min_minutes=450)

    assert result["available"] is True
    assert result["n_pairs"] == 100
    assert {r["signal"] for r in result["results"]} == {
        "performance_baseline",
        "performance_value_efficiency",
        "age_adjusted_performance",
    }
    assert "promotion_rule" in result


def test_backtest_degrades_when_required_fields_are_missing():
    result = evaluate_market_signals(pd.DataFrame([{"player_id": "x"}]))
    assert result["available"] is False
    assert "Missing required columns" in result["reason"]