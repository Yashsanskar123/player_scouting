from datetime import date

import pandas as pd
import pytest

from src.data import transfermarkt_link as link
from src.features import transfermarkt_context as ctx


def _write_sidecars(tmp_path, monkeypatch):
    pd.DataFrame([{
        "player_id": "abc", "tm_player_id": 1, "match_confidence": "High", "match_score": 36, "tm_id_shared": False,
        "tm_name": "Test Player", "date_of_birth": "2000-01-01", "country_of_citizenship": "Spain", "position": "Attack",
        "sub_position": "Centre-Forward", "foot": "left", "height_in_cm": 180, "contract_expiration_date": "2028-06-30",
        "agent_name": "Agent X", "current_club_name": "Club Y", "current_club_domestic_competition_id": "ES1",
        "tm_market_value_eur": 20_000_000, "tm_peak_value_eur": 25_000_000, "tm_last_season": 2025, "tm_url": "https://x",
    }]).to_csv(tmp_path / "tm_player_link.csv", index=False)
    pd.DataFrame({
        "tm_player_id": [1, 1, 1],
        "date": ["2025-06-01", "2026-01-01", "2026-06-01"],
        "market_value_in_eur": [10_000_000, 15_000_000, 20_000_000],
        "current_club_name": ["Club Y"] * 3,
    }).to_csv(tmp_path / "tm_valuations.csv", index=False)
    pd.DataFrame([
        {"tm_player_id": 1, "transfer_date": "2024-07-01", "transfer_season": "24/25", "from_club_id": 1, "to_club_id": 2,
         "from_club_name": "A", "to_club_name": "Club Y", "transfer_fee": 5_000_000.0, "market_value_in_eur": 4_000_000.0},
        {"tm_player_id": 1, "transfer_date": "2030-06-30", "transfer_season": "29/30", "from_club_id": 2, "to_club_id": 3,
         "from_club_name": "Club Y", "to_club_name": "Future", "transfer_fee": 0.0, "market_value_in_eur": None},
    ]).to_csv(tmp_path / "tm_transfers.csv", index=False)
    monkeypatch.setattr(ctx, "EXTERNAL_DIR", tmp_path)
    ctx.reload_cache()


def test_context_available_and_contract_status(tmp_path, monkeypatch):
    _write_sidecars(tmp_path, monkeypatch)
    out = ctx.get_context("abc", as_of=date(2026, 10, 2))
    assert out["available"] is True
    assert out["contract"]["expires"] == "2028-06-30"
    assert out["contract"]["status"] == "1-2 years left"
    assert out["market"]["pct_of_peak"] == 80.0
    assert out["market"]["change_12m_pct"] == 100.0
    # future-dated transfer rows (loan returns / placeholders) are excluded
    assert [t["to_club"] for t in out["transfers"]] == ["Club Y"]


def test_context_unavailable_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx, "EXTERNAL_DIR", tmp_path)  # empty folder
    ctx.reload_cache()
    assert ctx.get_context("anything") == {"available": False, "snapshot_note": ctx.SNAPSHOT_NOTE}
    _write_sidecars(tmp_path, monkeypatch)
    assert ctx.get_context("unknown-id")["available"] is False


def test_contract_block_expired_and_missing():
    assert ctx._contract_block(None, date(2026, 10, 2))["status"] == "Unknown"
    assert ctx._contract_block("2026-06-30", date(2026, 10, 2))["status"].startswith("Expired")
    assert ctx._contract_block("2027-01-31", date(2026, 10, 2))["status"] == "Expiring within 6 months"


def test_name_and_nation_normalisation():
    assert link.fold("Kylian Mbappé-Lottin") == "kylian mbappe lottin"
    assert link.nation_key("Korea Republic") == "south korea"
    assert link.season_start_year(2324) == 2023


def test_match_links_clear_case_and_refuses_ambiguous():
    project = pd.DataFrame([
        {"player_id": "p1", "long_name": "Kylian Mbappe Lottin", "short_name": "K. Mbappe", "nationality": "France",
         "height_cm": 182, "birth_year_est": 1998.0, "last_season": 2324},
        {"player_id": "p2", "long_name": "Pedro Gomez", "short_name": "P. Gomez", "nationality": "Spain",
         "height_cm": 180, "birth_year_est": 1995.0, "last_season": 2324},
    ])
    tm = pd.DataFrame([
        {"player_id": 10, "name": "Kylian Mbappé", "date_of_birth": "1998-12-20", "country_of_citizenship": "France", "height_in_cm": 178},
        {"player_id": 20, "name": "Pedro Gomez", "date_of_birth": "1995-03-01", "country_of_citizenship": "Spain", "height_in_cm": 180},
        {"player_id": 21, "name": "Pedro Gomez", "date_of_birth": "1995-04-01", "country_of_citizenship": "Spain", "height_in_cm": 180},
    ])
    out = link.match(project, tm).set_index("player_id")
    assert out.loc["p1", "tm_player_id"] == 10
    assert "p2" not in out.index  # two equally good candidates -> no guess


def test_bulk_and_outlook(tmp_path, monkeypatch):
    _write_sidecars(tmp_path, monkeypatch)
    info = ctx.bulk_contract_info(["abc", "nope"], as_of=date(2026, 10, 2))
    assert set(info) == {"abc"} and info["abc"]["contract_status"] == "1-2 years left"
    assert info["abc"]["tm_value_change_12m_pct"] == 100.0
    out = ctx.contract_outlook([{"player_id": "abc"}, {"player_id": "nope"}], as_of=date(2026, 10, 2))
    assert out["coverage"] == {"with_contract_data": 1, "roster_size": 2}
    assert out["buckets"]["within_24m"] == 1 and out["buckets"]["unknown"] == 1
