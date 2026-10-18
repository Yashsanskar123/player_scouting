import json
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine, inspect, text

from src.db.migrate import ensure_workflow_schema
from src.features import club_profile as cp
from src.features.club_dashboard import affordable_targets, watchlist_movers
from src.features.club_stats import roster_stats


# ------------------------------------------------------------ multi-club
@pytest.fixture()
def profile_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "PROFILE_PATH", tmp_path / "club_profile.json")
    return tmp_path / "club_profile.json"


def test_several_clubs_with_one_active(profile_file):
    cp.save_profile("Arsenal", "4-3-3", 100e6)
    cp.save_profile("Brentford", "4-2-3-1")
    assert cp.load_profile()["club_name"] == "Brentford"  # last saved becomes active
    assert [c["club_name"] for c in cp.list_profiles()["clubs"]] == ["Arsenal", "Brentford"]
    cp.set_active("Arsenal")
    assert cp.load_profile()["transfer_budget_eur"] == 100e6
    with pytest.raises(ValueError):
        cp.set_active("Nobody")
    cp.delete_profile()  # removes the active one; the other takes over
    assert cp.load_profile()["club_name"] == "Brentford"
    cp.delete_profile("Nobody")  # unknown: harmless
    cp.delete_profile("Brentford")
    assert cp.load_profile() is None and not profile_file.exists()


def test_old_single_club_file_is_read_and_upgraded(profile_file):
    profile_file.write_text(json.dumps({"club_name": "Arsenal", "formation": "4-3-3", "transfer_budget_eur": 5e7, "wage_budget_eur": None, "updated_at": "x"}))
    assert cp.load_profile()["club_name"] == "Arsenal"  # works without any migration step
    cp.save_profile("Chelsea", "4-3-3")
    assert {c["club_name"] for c in cp.list_profiles()["clubs"]} == {"Arsenal", "Chelsea"}
    assert json.loads(profile_file.read_text())["version"] == 2


def test_corrupt_profile_file_never_raises(profile_file):
    profile_file.write_text("{ not json")
    assert cp.load_profile() is None and cp.list_profiles() == {"active": None, "clubs": []}


def test_roster_stats():
    r = pd.DataFrame({"age_fifa": [20, 30], "performance_score": [60.0, 80.0], "value_eur": [1e6, 3e6], "canonical_position": ["ST", "CB"], "broad_position_group": ["Forward", "Defender"]})
    s = roster_stats(r)
    assert s["roster_size"] == 2 and s["average_age"] == 25.0 and s["squad_market_value_eur"] == 4e6 and s["young_players_share"] == 50.0
    assert s["by_position_group"]["Forward"]["average_performance"] == 60.0
    assert roster_stats(r.iloc[0:0])["average_age"] is None


# -------------------------------------------------------------- dashboard
def _season():
    rows = [("own1", "Me FC", "RB", 60, 25, 5e6, "High"), ("t1", "Other", "RB", 70, 24, 20e6, "High"), ("t2", "Other", "RB", 75, 24, 90e6, "High"),
            ("t3", "Other", "RB", 72, 34, 5e6, "High"), ("t4", "Other", "RB", 74, 22, 10e6, "Low"), ("t5", "Other", "ST", 80, 24, 10e6, "High")]
    return pd.DataFrame(rows, columns=["player_id", "club_name", "canonical_position", "performance_score", "age_fifa", "value_eur", "sample_reliability_tier"])


def test_affordable_targets_respect_budget_age_reliability_and_position():
    need = [{"need": "RB depth", "severity": "HIGH", "recruitment_filter": {"canonical_position": "RB"}}]
    out = affordable_targets(_season(), "Me FC", need, 50e6)
    assert [c["player_id"] for c in out[0]["candidates"]] == ["t1"]  # t2 too dear, t3 too old, t4 unreliable, t5 wrong position
    assert out[0]["bar"] == 60.0 or out[0]["bar"] == 60
    assert [c["player_id"] for c in affordable_targets(_season(), "Me FC", need, None)[0]["candidates"]] == ["t2", "t1"]  # no budget: best first
    assert affordable_targets(_season(), "Me FC", [{"need": "x"}], 1e6) == []  # needs without a position are skipped


def test_watchlist_movers_flag_real_changes_only():
    facts = pd.DataFrame([("a", 2324, 60.0, "A", "X"), ("a", 2425, 70.0, "A", "X"), ("b", 2324, 60.0, "B", "X"), ("b", 2425, 61.0, "B", "X"),
                          ("c", 2425, 90.0, "C", "X")], columns=["player_id", "season", "performance_score", "short_name", "club_name"])
    out = watchlist_movers(["a", "b", "c"], facts, 2425)
    assert [m["player_id"] for m in out] == ["a"] and out[0]["change"] == 10.0 and out[0]["direction"] == "up"
    assert watchlist_movers([], facts, 2425) == []


# --------------------------------------------------------------- migration
def test_workflow_migration_keeps_existing_rows_and_is_idempotent():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table shortlist_entries (id integer primary key, shortlist_id int, player_id text, status text, notes text, rating int, added_at text)"))
        c.execute(text("insert into shortlist_entries values (1, 1, 'p', 'Monitoring', 'old note', 4, '2026-01-01')"))
    assert ensure_workflow_schema(engine)["columns_added"] == ["owner", "due_date", "next_action"]
    assert ensure_workflow_schema(engine)["columns_added"] == []
    with engine.connect() as c:
        assert c.execute(text("select status, notes, rating, owner from shortlist_entries")).fetchone() == ("Monitoring", "old note", 4, None)
    assert "entry_events" in inspect(engine).get_table_names()
