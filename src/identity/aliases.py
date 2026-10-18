"""Player-id alias layer: merge duplicate ids safely and keep old ids working.

data/mappings/player_id_aliases.csv maps alias_id -> canonical_id.
  * apply_aliases(df)      rewrites player_id in a DataFrame (no-op without the file)
  * resolve_player_id(pid) maps an old id to its canonical id
  * remap_database(engine) re-points shortlist/squad/note rows to the canonical id
  * python -m src.identity.aliases apply   rewrites processed CSV, TM sidecar and DB (idempotent)
"""
from __future__ import annotations

import shutil
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[2]
ALIAS_PATH = ROOT / "data" / "mappings" / "player_id_aliases.csv"


@lru_cache(maxsize=1)
def load_aliases() -> dict[str, str]:
    if not ALIAS_PATH.exists():
        return {}
    raw = pd.read_csv(ALIAS_PATH, dtype=str)
    mapping = dict(zip(raw["alias_id"], raw["canonical_id"]))
    for alias in list(mapping):  # resolve chains defensively
        seen = {alias}
        while mapping[alias] in mapping and mapping[alias] not in seen:
            seen.add(mapping[alias])
            mapping[alias] = mapping[mapping[alias]]
    return mapping


def reload_aliases() -> None:
    load_aliases.cache_clear()


def resolve_player_id(player_id: str) -> str:
    return load_aliases().get(player_id, player_id)


def apply_aliases(df: pd.DataFrame) -> pd.DataFrame:
    mapping = load_aliases()
    if not mapping or "player_id" not in df.columns:
        return df
    df = df.copy()
    df["player_id"] = df["player_id"].map(lambda x: mapping.get(x, x))
    return df


def remap_database(engine) -> dict:
    """Idempotent. Keeps the canonical row when both ids exist in one shortlist/squad."""
    mapping = load_aliases()
    counts = {"shortlist_entries": 0, "squad_players": 0, "scout_notes": 0, "player_season_facts": 0, "player_identity": 0}
    if not mapping:
        return counts
    with engine.begin() as conn:
        tables = set(inspect(conn).get_table_names())
        for alias, canon in mapping.items():
            p = {"a": alias, "c": canon}
            if "shortlist_entries" in tables:
                counts["shortlist_entries"] += conn.execute(text(
                    "UPDATE shortlist_entries SET player_id=:c WHERE player_id=:a AND shortlist_id NOT IN "
                    "(SELECT shortlist_id FROM shortlist_entries WHERE player_id=:c)"), p).rowcount
                conn.execute(text("DELETE FROM shortlist_entries WHERE player_id=:a"), p)
            if "squad_players" in tables:
                counts["squad_players"] += conn.execute(text(
                    "UPDATE squad_players SET player_id=:c WHERE player_id=:a AND squad_id NOT IN "
                    "(SELECT squad_id FROM squad_players WHERE player_id=:c)"), p).rowcount
                conn.execute(text("DELETE FROM squad_players WHERE player_id=:a"), p)
            if "scout_notes" in tables:
                counts["scout_notes"] += conn.execute(text("UPDATE scout_notes SET player_id=:c WHERE player_id=:a"), p).rowcount
            if "player_season_facts" in tables:
                counts["player_season_facts"] += conn.execute(text("UPDATE player_season_facts SET player_id=:c WHERE player_id=:a"), p).rowcount
            if "player_identity" in tables:
                counts["player_identity"] += conn.execute(text("DELETE FROM player_identity WHERE player_id=:a"), p).rowcount
    return counts


def _apply_all() -> None:
    from src.db.session import engine
    processed = ROOT / "data" / "cleaned" / "fifa_fbref_merged_processed_v2.csv"
    backup_dir = ROOT / "data" / "cleaned" / "backup"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / "fifa_fbref_merged_processed_v2.pre_alias.csv"
    if not backup.exists():
        shutil.copy2(processed, backup)
    df = pd.read_csv(processed, low_memory=False)
    before = df["player_id"].nunique()
    df = apply_aliases(df)
    df.to_csv(processed, index=False)
    print(f"processed CSV: unique player_id {before} -> {df['player_id'].nunique()} (backup: {backup.name})")

    link_path = ROOT / "data" / "external" / "tm_player_link.csv"
    if link_path.exists():
        link = pd.read_csv(link_path, dtype={"player_id": str})
        link = apply_aliases(link).drop_duplicates("player_id")
        link["tm_id_shared"] = link.duplicated("tm_player_id", keep=False)
        link.to_csv(link_path, index=False)
        print(f"TM link rows: {len(link)}, still shared: {int(link['tm_id_shared'].sum())}")
    print("database re-pointed rows:", remap_database(engine))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        _apply_all()
    else:
        raise SystemExit(__doc__)
