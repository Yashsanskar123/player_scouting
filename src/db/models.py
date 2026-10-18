"""Relational tables (spec section 3/45-47).

Architecture note: the 135+ per-player statistical columns are NOT
hand-normalized into 15 joined tables (player_passing, player_shooting,
etc.) as the spec literally lists. For an analytics workload where nearly
every query needs most of those columns together (percentiles, role fit,
scoring all read across passing+shooting+defending simultaneously), a
wide fact table -- `player_season_facts`, created directly from the
processed DataFrame via `to_sql` in db/ingest.py -- is the standard
analytics-engineering pattern (a denormalized fact table + star-schema
dimensions), not an anti-pattern. Splitting it into 15 tables would mean
15 joins on every single API request for no query-planning benefit here.

What DOES belong as real relational, ORM-modeled tables is the workflow
state that's genuinely transactional: player identity, shortlists, squad
composition, and scout notes. Those are declared below.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class Season(Base):
    """Season dimension for consistent longitudinal analytics context."""
    __tablename__ = "seasons"

    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(16), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="completed")


class PlayerIdentity(Base):
    __tablename__ = "player_identity"

    player_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    identity_confidence: Mapped[str] = mapped_column(String(8))
    short_name: Mapped[str | None] = mapped_column(String(128))
    long_name: Mapped[str | None] = mapped_column(String(256))
    nationality_name: Mapped[str | None] = mapped_column(String(64))
    born_fifa: Mapped[float | None] = mapped_column(Float)
    preferred_foot: Mapped[str | None] = mapped_column(String(8))
    first_season: Mapped[int | None] = mapped_column(Integer)
    last_season: Mapped[int | None] = mapped_column(Integer)
    seasons_observed: Mapped[int | None] = mapped_column(Integer)


class Shortlist(Base):
    __tablename__ = "shortlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    entries: Mapped[list["ShortlistEntry"]] = relationship(back_populates="shortlist", cascade="all, delete-orphan")


# Recruitment workflow statuses (spec section 45)
RECRUITMENT_STATUSES = [
    "Discovery", "Monitoring", "Shortlisted", "Analyst Review",
    "Scout Review", "Final Target", "Negotiation", "Rejected", "Signed",
]


class ShortlistEntry(Base):
    __tablename__ = "shortlist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shortlist_id: Mapped[int] = mapped_column(ForeignKey("shortlists.id"))
    player_id: Mapped[str] = mapped_column(String(12), ForeignKey("player_identity.player_id"))
    status: Mapped[str] = mapped_column(String(32), default="Discovery")
    notes: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    added_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    # Workflow fields (added later; nullable so older databases migrate without data loss).
    owner: Mapped[str | None] = mapped_column(String(64))
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    next_action: Mapped[str | None] = mapped_column(String(255))

    shortlist: Mapped["Shortlist"] = relationship(back_populates="entries")


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    formation: Mapped[str] = mapped_column(String(16), default="4-3-3")
    budget_eur: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    players: Mapped[list["SquadPlayer"]] = relationship(back_populates="squad", cascade="all, delete-orphan")


class SquadPlayer(Base):
    __tablename__ = "squad_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    squad_id: Mapped[int] = mapped_column(ForeignKey("squads.id"))
    player_id: Mapped[str] = mapped_column(String(12), ForeignKey("player_identity.player_id"))
    assigned_position: Mapped[str | None] = mapped_column(String(8))
    depth_role: Mapped[str | None] = mapped_column(String(16))  # starter / rotation / backup / prospect

    squad: Mapped["Squad"] = relationship(back_populates="players")


class ScoutNote(Base):
    __tablename__ = "scout_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(String(12), ForeignKey("player_identity.player_id"))
    author: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class User(Base):
    """Platform user (only used when SCOUTIQ_AUTH_MODE=on)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="analyst")
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    """Append-only record of who did what. Never stores request bodies or secrets."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    username: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str | None] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(64), index=True)
    method: Mapped[str | None] = mapped_column(String(8))
    path: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[int | None] = mapped_column(Integer)
    entity: Mapped[str | None] = mapped_column(String(128))
    ip: Mapped[str | None] = mapped_column(String(64))


class EntryEvent(Base):
    """Timeline of changes to a shortlist entry (status, rating, owner, due date, next action, notes)."""
    __tablename__ = "entry_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(Integer, index=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, index=True)
    actor: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(24))
    detail: Mapped[str | None] = mapped_column(String(255))

