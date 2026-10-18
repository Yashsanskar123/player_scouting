"""Link ScoutIQ players to Transfermarkt and write SIDECAR files.

Nothing in the processed ScoutIQ dataset is modified. Output (data/external/):
  tm_player_link.csv   one row per ScoutIQ player_id that was matched
  tm_valuations.csv    market-value history for matched players
  tm_transfers.csv     transfer history for matched players

Usage:
  python -m src.data.transfermarkt_link <folder with Transfermarkt *.csv.gz files>
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "cleaned" / "fifa_fbref_merged_processed_v2.csv"
OUT_DIR = ROOT / "data" / "external"

NATION_ALIASES = {
    "korea republic": "south korea",
    "republic of ireland": "ireland",
    "china pr": "china",
    "cote d'ivoire": "cote d'ivoire",
    "turkiye": "turkey",
    "czech republic": "czech republic",
    "bosnia herzegovina": "bosnia-herzegovina",
    "bosnia and herzegovina": "bosnia-herzegovina",
    "dr congo": "dr congo",
    "united states": "united states",
}
PARTICLES = {"de", "da", "do", "dos", "das", "van", "von", "der", "den", "di", "del", "la", "le", "el", "al", "bin", "jr", "junior"}


def fold(text) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z' ]+", " ", text.replace("-", " ")).lower()
    return re.sub(r"\s+", " ", text).strip()


def nation_key(value) -> str:
    key = fold(value)
    return NATION_ALIASES.get(key, key)


def tokens(text: str) -> set[str]:
    return {t for t in fold(text).split() if len(t) > 1}


def season_start_year(code: int) -> int:
    code = int(code)
    yy = code // 100
    return 2000 + yy if yy < 90 else 1900 + yy


def build_project_players() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED, low_memory=False)
    df["start_year"] = df["season"].map(season_start_year)
    df["birth_year_est"] = df["start_year"] - df["age_fifa"]
    df = df.sort_values("season")
    agg = df.groupby("player_id").agg(
        long_name=("long_name", "last"),
        short_name=("short_name", "last"),
        nationality=("nationality_name", "last"),
        height_cm=("height_cm", "last"),
        birth_year_est=("birth_year_est", "median"),
        last_season=("season", "last"),
    ).reset_index()
    return agg


def match(project: pd.DataFrame, tm: pd.DataFrame) -> pd.DataFrame:
    tm = tm[tm["date_of_birth"].notna() & tm["name"].notna()].copy()
    tm["birth_year"] = pd.to_datetime(tm["date_of_birth"], errors="coerce").dt.year
    tm = tm[tm["birth_year"].notna()].reset_index(drop=True)
    recs = []
    index: dict[str, list[int]] = {}
    for i, r in enumerate(tm.itertuples(index=False)):
        tok = tokens(r.name)
        core = frozenset({t for t in tok if t not in PARTICLES} or tok)
        recs.append((int(r.player_id), int(r.birth_year), nation_key(r.country_of_citizenship), r.height_in_cm, core))
        for t in core:
            index.setdefault(t, []).append(i)

    rows = []
    for p in project.itertuples(index=False):
        ptok = tokens(p.long_name) | tokens(p.short_name)
        if not ptok or pd.isna(p.birth_year_est):
            continue
        short_tok = tokens(p.short_name)
        pnat = nation_key(p.nationality)
        seen: set[int] = set()
        for t in ptok:
            seen.update(index.get(t, ()))
        best = []
        for i in seen:
            tid, by, cnat, cheight, core = recs[i]
            if abs(by - p.birth_year_est) > 1.5 or not core:
                continue
            if core <= ptok:
                name_score = 3 if len(core) >= 2 else 2
            elif short_tok & core and len(core - ptok) <= 1:
                name_score = 1
            else:
                continue
            score = name_score * 10
            score += 4 if abs(by - p.birth_year_est) <= 0.5 else 1
            if cnat and cnat == pnat:
                score += 4
            elif cnat and pnat:
                score -= 3
            if pd.notna(p.height_cm) and pd.notna(cheight):
                diff = abs(float(cheight) - float(p.height_cm))
                score += 3 if diff <= 2 else (-4 if diff > 5 else 0)
            best.append((score, tid))
        if not best:
            continue
        best.sort(reverse=True)
        top = best[0]
        margin = top[0] - best[1][0] if len(best) > 1 else 99
        if margin < 4:
            continue  # ambiguous: refuse to guess
        if top[0] >= 31:
            conf = "High"
        elif top[0] >= 24:
            conf = "Medium"
        else:
            continue
        rows.append({"player_id": p.player_id, "tm_player_id": top[1], "match_confidence": conf, "match_score": top[0]})
    return pd.DataFrame(rows)


def main(src: Path) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    players = pd.read_csv(src / "players.csv.gz")
    project = build_project_players()
    links = match(project, players)
    # ScoutIQ sometimes holds two ids for one real player; keep both linked and flag them
    links["tm_id_shared"] = links.duplicated("tm_player_id", keep=False)

    keep = ["player_id", "name", "date_of_birth", "country_of_citizenship", "position", "sub_position", "foot",
            "height_in_cm", "contract_expiration_date", "agent_name", "current_club_name",
            "current_club_domestic_competition_id", "market_value_in_eur", "highest_market_value_in_eur", "last_season", "url"]
    enrich = players[keep].rename(columns={"player_id": "tm_player_id", "name": "tm_name", "last_season": "tm_last_season", "url": "tm_url",
                                           "market_value_in_eur": "tm_market_value_eur", "highest_market_value_in_eur": "tm_peak_value_eur"})
    out = links.merge(enrich, on="tm_player_id", how="left")
    out["date_of_birth"] = pd.to_datetime(out["date_of_birth"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["contract_expiration_date"] = pd.to_datetime(out["contract_expiration_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out.to_csv(OUT_DIR / "tm_player_link.csv", index=False)

    ids = set(out["tm_player_id"])
    val = pd.read_csv(src / "player_valuations.csv.gz", usecols=["player_id", "date", "market_value_in_eur", "current_club_name"])
    val = val[val["player_id"].isin(ids)].rename(columns={"player_id": "tm_player_id"})
    val["date"] = pd.to_datetime(val["date"]).dt.strftime("%Y-%m-%d")
    val.to_csv(OUT_DIR / "tm_valuations.csv", index=False)

    tr = pd.read_csv(src / "transfers.csv.gz")
    tr = tr[tr["player_id"].isin(ids)].rename(columns={"player_id": "tm_player_id"})
    tr.drop(columns=["player_name"], errors="ignore").to_csv(OUT_DIR / "tm_transfers.csv", index=False)

    print(f"ScoutIQ players: {len(project)}  matched: {len(out)} ({len(out)/len(project):.1%})")
    print(out["match_confidence"].value_counts().to_dict())
    print(f"valuation rows: {len(val)}  transfer rows: {len(tr)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
