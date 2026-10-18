"""Loads the processed pipeline output into the database (spec section
58's "Analytics Tables" step). Run this after `pipeline_v2.run_pipeline_v2`
produces the processed CSV, or call `full_refresh()` to do both in one
step -- this is the operation a scheduled data-refresh job would call.
"""
from __future__ import annotations

import pandas as pd

from src.db.session import engine, SessionLocal, Base
from src.db.models import PlayerIdentity, Season
from src.identity.resolve_identity import build_player_identity_table


FACT_TABLE = "player_season_facts"


def load_processed_data(processed_path: str) -> pd.DataFrame:
    df = pd.read_csv(processed_path, low_memory=False)
    return df


def ingest_fact_table(df: pd.DataFrame) -> int:
    """Bulk-load the wide analytics fact table. `if_exists='replace'` is
    correct here: this table is fully rebuilt from the pipeline's output
    every refresh, it is never hand-edited, so there's nothing to merge.
    """
    df.to_sql(FACT_TABLE, engine, if_exists="replace", index=False, chunksize=2000)
    return len(df)


def ingest_season_dimension(df: pd.DataFrame) -> int:
    """Rebuild the season dimension from the fact data."""
    if "season" not in df.columns:
        return 0
    Base.metadata.create_all(engine, tables=[Season.__table__])
    seasons = sorted(pd.to_numeric(df["season"], errors="coerce").dropna().astype(int).unique().tolist())
    session = SessionLocal()
    try:
        session.query(Season).delete()
        for value in seasons:
            text_value = str(value)
            start = int(text_value[:2])
            end = int(text_value[2:])
            label = f"{2000 + start}/{2000 + end}"
            session.add(Season(season=value, label=label, status="completed"))
        if seasons:
            latest = seasons[-1]
            row = session.get(Season, latest)
            if row:
                row.status = "current"
        session.commit()
        return len(seasons)
    finally:
        session.close()


def ingest_player_identity(df: pd.DataFrame) -> int:
    Base.metadata.create_all(engine, tables=[PlayerIdentity.__table__])
    identity_df = build_player_identity_table(df)

    session = SessionLocal()
    try:
        session.query(PlayerIdentity).delete()
        records = identity_df.to_dict(orient="records")
        for r in records:
            session.add(PlayerIdentity(
                player_id=r["player_id"],
                identity_confidence=r.get("identity_confidence"),
                short_name=r.get("short_name"),
                long_name=r.get("long_name"),
                nationality_name=r.get("nationality_name"),
                born_fifa=r.get("born_fifa"),
                preferred_foot=r.get("preferred_foot"),
                first_season=r.get("first_season"),
                last_season=r.get("last_season"),
                seasons_observed=r.get("seasons_observed"),
            ))
        session.commit()
        return len(records)
    finally:
        session.close()


def create_all_tables() -> None:
    Base.metadata.create_all(engine)


def full_refresh(processed_path: str) -> dict:
    create_all_tables()
    df = load_processed_data(processed_path)
    fact_rows = ingest_fact_table(df)
    identity_rows = ingest_player_identity(df)
    season_rows = ingest_season_dimension(df)
    return {"fact_table_rows": fact_rows, "identity_rows": identity_rows, "season_rows": season_rows}


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/cleaned/fifa_fbref_merged_processed_v2.csv"
    result = full_refresh(path)
    print(result)
