"""Demo mode: fill a fresh install with a realistic club, shortlists, owners, deadlines and history.

  python -m src.demo.seed                      seed (idempotent: does nothing if demo data already exists)
  python -m src.demo.seed --club "Chelsea"     choose the demo club
  python -m src.demo.seed --reset              remove everything this tool created
  python -m src.demo.seed --users              also create one demo user per role (needs SCOUTIQ_DEMO_PASSWORD)

Everything is built from the platform's own data: the club's real roster, its audited needs, and real affordable
candidates. Only the workflow details (owners, dates, wording of notes) are invented, and all demo rows are marked
("Demo: " list names, "demo" note author) so they can be removed cleanly.
"""
from __future__ import annotations

import argparse
import os
from datetime import date, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from src.db.models import EntryEvent, ScoutNote, Shortlist, ShortlistEntry
from src.features.club_dashboard import affordable_targets

DEMO_PREFIX = "Demo: "
DEMO_AUTHOR = "demo"
OWNERS = ["Sam", "Priya", "Alex"]
STAGES = [  # status, rating, days until due, next action
    ("Scout Review", 4, -3, "Book a live viewing of the next home match"),
    ("Shortlisted", 4, 2, "Ask the analyst team for a comparison against the incumbent"),
    ("Monitoring", 3, 9, "Re-check minutes and contract situation in a month"),
]
DEMO_USERS = {"demo-admin": "admin", "demo-director": "director", "demo-scout": "scout", "demo-analyst": "analyst"}


def _latest_season_with(facts: pd.DataFrame, club: str) -> int | None:
    seasons = facts.loc[facts["club_name"] == club, "season"]
    return int(seasons.max()) if len(seasons) else None


def demo_exists(session: Session) -> bool:
    return session.query(Shortlist).filter(Shortlist.name.like(f"{DEMO_PREFIX}%")).count() > 0


def reset_demo(session: Session) -> dict:
    lists = session.query(Shortlist).filter(Shortlist.name.like(f"{DEMO_PREFIX}%")).all()
    entry_ids = [e.id for sl in lists for e in sl.entries]
    events = session.query(EntryEvent).filter(EntryEvent.entry_id.in_(entry_ids)).delete(synchronize_session=False) if entry_ids else 0
    notes = session.query(ScoutNote).filter(ScoutNote.author == DEMO_AUTHOR).delete(synchronize_session=False)
    for sl in lists:
        session.delete(sl)  # entries go with the list (cascade)
    session.commit()
    return {"shortlists": len(lists), "entries": len(entry_ids), "events": int(events), "notes": int(notes)}


def seed_demo(session: Session, facts: pd.DataFrame, club: str = "Arsenal", season: int | None = None, transfer_budget_eur: float = 80e6,
              today: date | None = None, write_profile: bool = True) -> dict:
    """Create the demo data. Returns what was created, or {"created": False} if demo data already exists."""
    if demo_exists(session):
        return {"created": False, "reason": "Demo data already exists. Use --reset to remove it first."}
    season = season if season is not None else _latest_season_with(facts, club)
    if season is None:
        raise ValueError(f"'{club}' has no players in the data.")
    season_df = facts[facts["season"] == season]
    roster = season_df[season_df["club_name"] == club]
    if roster.empty:
        raise ValueError(f"'{club}' has no players in season {season}.")

    from src.features.squad_audit import audit_squad
    priorities = audit_squad(roster, formation="4-3-3").get("recruitment_priorities", [])[:3]
    needs = affordable_targets(season_df, club, priorities, transfer_budget_eur, per_need=3)
    today = today or date.today()
    created = {"created": True, "club": club, "season": season, "shortlists": 0, "entries": 0, "notes": 0}
    names = season_df.drop_duplicates("player_id").set_index("player_id")

    for need in needs:
        if not need["candidates"]:
            continue
        sl = Shortlist(name=f"{DEMO_PREFIX}{need['position']} targets")
        session.add(sl)
        session.flush()
        created["shortlists"] += 1
        for i, cand in enumerate(need["candidates"]):
            status, rating, due_in, action = STAGES[i % len(STAGES)]
            owner = OWNERS[i % len(OWNERS)]
            entry = ShortlistEntry(shortlist_id=sl.id, player_id=cand["player_id"], status=status, rating=rating, owner=owner,
                                   due_date=today + timedelta(days=due_in), next_action=action, notes=f"Demo entry for the {need['position']} need.")
            session.add(entry)
            session.flush()
            created["entries"] += 1
            for kind, detail in (("added", "Added as Discovery"), ("status", f"Discovery -> {status}"), ("owner", f"unassigned -> {owner}"),
                                 ("due", f"none -> {(today + timedelta(days=due_in)).isoformat()}")):
                session.add(EntryEvent(entry_id=entry.id, actor=DEMO_AUTHOR, kind=kind, detail=detail))
            perf = cand.get("performance_score")
            session.add(ScoutNote(player_id=cand["player_id"], author=DEMO_AUTHOR,
                                  note=(f"Demo note: {cand['short_name']} rates {perf:.0f} for a {need['position']} in the model; "
                                        "verify recent minutes, contract and style fit before approaching.") if perf is not None else "Demo note: check recent minutes and contract."))
            created["notes"] += 1
    session.commit()

    if write_profile:
        from src.features.club_profile import save_profile
        save_profile(club, "4-3-3", transfer_budget_eur)
    return created


def seed_users(session: Session, password: str) -> list[str]:
    from src.auth import service
    made = []
    for username, role in DEMO_USERS.items():
        if service.get_user(session, username) is None:
            service.create_user(session, username, password, role, f"Demo {role}")
            made.append(username)
    return made


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--club", default="Arsenal")
    parser.add_argument("--reset", action="store_true", help="remove the demo data")
    parser.add_argument("--users", action="store_true", help="create one demo user per role (password from SCOUTIQ_DEMO_PASSWORD)")
    args = parser.parse_args(argv)
    from src.auth.service import ensure_auth_tables
    from src.db.migrate import ensure_workflow_schema
    from src.db.session import SessionLocal, engine
    from src.services.data_store import store
    ensure_auth_tables()
    ensure_workflow_schema(engine)
    with SessionLocal() as session:
        if args.reset:
            print("removed:", reset_demo(session))
            return 0
        print(seed_demo(session, store.facts, club=args.club))
        if args.users:
            password = os.getenv("SCOUTIQ_DEMO_PASSWORD", "")
            if len(password) < 10:
                print("Set SCOUTIQ_DEMO_PASSWORD (10+ characters) to create demo users; none were created.")
                return 1
            print("demo users created:", seed_users(session, password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
