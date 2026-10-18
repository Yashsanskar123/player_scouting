"""In-memory analytics data store.

The processed fact table (~28k rows x ~190 cols, well under 50MB) is kept
in memory as a pandas DataFrame after being loaded from the database once
at startup, rather than re-read from disk/DB on every request (spec
section 51's <500ms target rules out a fresh CSV/DB read per call).

This is the standard pattern for an analytics service backed by a
periodically-refreshed warehouse table: the DB is the durable source of
truth and refresh target (what `db/ingest.py` populates); the service
holds a fast in-memory working copy for serving. Calling `reload()` (e.g.
after a pipeline run) re-syncs from the DB without restarting the process.
"""
from __future__ import annotations

import threading
import time

import pandas as pd
from sqlalchemy import inspect

from src.db.session import engine
from src.db.ingest import FACT_TABLE


class DataStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._facts: pd.DataFrame = pd.DataFrame()
        self._loaded_at: float | None = None

    def reload(self) -> None:
        with self._lock:
            with engine.connect() as conn:
                # Database-neutral check (works on SQLite and PostgreSQL).
                if not inspect(conn).has_table(FACT_TABLE):
                    self._facts = pd.DataFrame()
                    return
                self._facts = pd.read_sql_table(FACT_TABLE, conn)
            self._loaded_at = time.time()

    @property
    def facts(self) -> pd.DataFrame:
        if self._facts.empty and self._loaded_at is None:
            self.reload()
        return self._facts

    @property
    def loaded_at(self) -> float | None:
        return self._loaded_at

    def available_seasons(self) -> list[int]:
        df = self.facts
        if df.empty or "season" not in df.columns:
            return []
        return sorted(pd.to_numeric(df["season"], errors="coerce").dropna().astype(int).unique().tolist())

    def current_season(self) -> int | None:
        seasons = self.available_seasons()
        return seasons[-1] if seasons else None

    def season(self, season: int | None = None) -> pd.DataFrame:
        df = self.facts
        if df.empty or "season" not in df.columns:
            return df
        selected = self.current_season() if season is None else int(season)
        return df[df["season"] == selected]

    def latest_season(self) -> pd.DataFrame:
        return self.season()


store = DataStore()
