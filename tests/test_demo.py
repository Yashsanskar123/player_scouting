from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.models import Base, EntryEvent, ScoutNote, Shortlist, ShortlistEntry
from src.demo import seed as demo


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


@pytest.fixture()
def facts_and_targets(pipeline_df, monkeypatch, tmp_path):
    from src.features import club_profile
    monkeypatch.setattr(club_profile, "PROFILE_PATH", tmp_path / "club.json")
    api_test_df = pipeline_df
    club = api_test_df["club_name"].dropna().iloc[0]
    players = api_test_df[api_test_df["club_name"] != club].drop_duplicates("player_id").head(4)
    cands = [{"player_id": r.player_id, "short_name": r.short_name, "performance_score": float(r.performance_score)} for r in players.itertuples()]
    monkeypatch.setattr(demo, "affordable_targets", lambda *a, **k: [{"position": "ST", "candidates": cands[:3]}, {"position": "CB", "candidates": cands[3:]}, {"position": "GK", "candidates": []}])
    return api_test_df, club


def test_seed_creates_marked_workflow_data_with_history(session, facts_and_targets):
    facts, club = facts_and_targets
    out = demo.seed_demo(session, facts, club=club, today=date(2026, 10, 5))
    assert out["created"] is True and out["shortlists"] == 2 and out["entries"] == 4 and out["notes"] == 4  # the empty GK need is skipped
    assert {s.name for s in session.query(Shortlist)} == {"Demo: ST targets", "Demo: CB targets"}
    entries = session.query(ShortlistEntry).all()
    assert all(e.owner and e.due_date and e.next_action and e.status in {"Scout Review", "Shortlisted", "Monitoring"} for e in entries)
    assert any(e.due_date < date(2026, 10, 5) for e in entries)  # at least one overdue task, so the dashboard has something to show
    assert session.query(EntryEvent).count() == 16 and all(n.author == "demo" for n in session.query(ScoutNote))


def test_seed_is_idempotent_and_reset_removes_only_demo_data(session, facts_and_targets):
    facts, club = facts_and_targets
    session.add(Shortlist(name="Real list"))
    session.commit()
    demo.seed_demo(session, facts, club=club)
    assert demo.seed_demo(session, facts, club=club)["created"] is False and session.query(Shortlist).count() == 3
    removed = demo.reset_demo(session)
    assert removed["shortlists"] == 2 and removed["entries"] == 4 and removed["notes"] == 4
    assert [s.name for s in session.query(Shortlist)] == ["Real list"]
    assert session.query(ShortlistEntry).count() == 0 and session.query(EntryEvent).count() == 0 and session.query(ScoutNote).count() == 0


def test_seed_sets_the_demo_club_profile_and_rejects_unknown_clubs(session, facts_and_targets):
    from src.features.club_profile import load_profile
    facts, club = facts_and_targets
    demo.seed_demo(session, facts, club=club)
    assert load_profile()["club_name"] == club
    demo.reset_demo(session)
    with pytest.raises(ValueError):
        demo.seed_demo(session, facts, club="Nowhere FC")
    assert session.query(Shortlist).count() == 0  # a failed seed leaves nothing behind


def test_demo_users_need_a_real_password_and_are_not_duplicated(session):
    assert demo.seed_users(session, "demo-password-123") == ["demo-admin", "demo-director", "demo-scout", "demo-analyst"]
    assert demo.seed_users(session, "demo-password-123") == []
