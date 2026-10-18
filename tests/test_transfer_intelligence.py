import pandas as pd

from src.features.transfer_intelligence import build_transfer_intelligence


def test_transfer_intelligence_uses_observable_signals_and_flags_missing_contract_data():
    df = pd.DataFrame([
        {
            "player_id": "p1", "season": 2324, "club_name": "Club A", "league_name": "League A",
            "value_eur": 10_000_000, "fair_value_eur": 13_000_000, "value_gap_pct": 30,
            "wage_eur": 50_000, "performance_score": 82, "development_potential": 86,
            "age_fifa": 22, "recruitment_risk_score": 20,
        },
        {
            "player_id": "p1", "season": 2425, "club_name": "Club B", "league_name": "League B",
            "value_eur": 12_000_000, "fair_value_eur": 15_000_000, "value_gap_pct": 25,
            "wage_eur": 50_000, "performance_score": 84, "development_potential": 87,
            "age_fifa": 23, "recruitment_risk_score": 22,
        },
    ])

    result = build_transfer_intelligence(df, "p1")

    assert result["opportunity_score"] is not None
    assert result["club_changes"] == 1
    assert result["league_changes"] == 1
    assert result["contract_status"] == "UNAVAILABLE"
    assert result["contract_expiry"] is None
    assert result["release_clause_eur"] is None
    assert result["data_available"]["contract_expiry"] is False
    assert result["data_available"]["transfer_fee"] is False


def test_transfer_intelligence_does_not_claim_a_value_opportunity_when_gap_is_negative():
    df = pd.DataFrame([{
        "player_id": "p2", "season": 2425, "club_name": "Club A", "league_name": "League A",
        "value_eur": 20_000_000, "fair_value_eur": 15_000_000, "value_gap_pct": -25,
        "wage_eur": 100_000, "performance_score": 70, "development_potential": 72,
        "age_fifa": 29, "recruitment_risk_score": 35,
    }])

    result = build_transfer_intelligence(df, "p2")

    assert result["opportunity_score"] < 60
    assert any("below" in item.lower() for item in result["concerns"])
