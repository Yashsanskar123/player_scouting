"""Database engine/session setup.

Defaults to a local SQLite file so the project runs with zero external
services for development and for this deliverable. Production deployment
is a one-line change: set DATABASE_URL to a Postgres DSN
(e.g. postgresql+psycopg2://user:pass@host:5432/scoutiq) -- nothing else
in the codebase references SQLite directly, since all access goes through
SQLAlchemy Core/ORM.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from src.config.settings import DATA_DIR

DEFAULT_SQLITE_PATH = DATA_DIR / "scoutiq.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
