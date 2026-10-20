import pandas as pd

from src.validation.position_score_backtest import evaluate_position_scores


def test_position_score_backtest_reports_gk_and_cb():
    rows = []
    for player_index in range(80):
        for season in [2122, 2223, 2324]:
            position = "GK" if player_index < 40 else "CB"
            score = 45 + (player_index % 35)
            rows.append({
                "player_id": f"p{player_index}",
                "season": season,
                "canonical_position": position,
                "performance_score": score,
                "playing_time_min": 700 + player_index * 5,
                "value_eur": 100_000 + player_index * 30_000,
            })

    result = evaluate_position_scores(pd.DataFrame(rows))

    assert result["available"]
    assert {item["position"] for item in result["positions"]} == {"GK", "CB"}
    assert all(item["available"] for item in result["positions"])
    assert all("year_to_year_score_stability" in item for item in result["positions"])
    assert all("spearman_score_vs_next_minutes" in item for item in result["positions"])
    assert all("spearman_score_vs_market_value" in item for item in result["positions"])


def test_position_score_backtest_handles_missing_fields():
    result = evaluate_position_scores(pd.DataFrame([{"player_id": "x"}]))
    assert not result["available"]