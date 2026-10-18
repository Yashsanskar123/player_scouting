"""Propose safe merges of duplicate ScoutIQ player_ids using Transfermarkt links.

Writes data/mappings/player_id_aliases.csv (alias_id -> canonical_id) and
data/mappings/player_id_alias_skipped.csv (groups left alone, with the reason).
A group is merged only when ALL of these hold:
  * every link to the Transfermarkt player is High confidence
  * the ids never appear in the same season
  * estimated birth years agree (<=1) and name tokens overlap
  * nationality agrees after spelling normalisation, OR (real nationality change)
    every id's height is within 3 cm of the Transfermarkt height
Usage: python -m src.identity.propose_aliases
"""
from __future__ import annotations

import pandas as pd

from src.data.transfermarkt_link import fold, season_start_year
from src.identity.aliases import ALIAS_PATH, ROOT

PROCESSED = ROOT / "data" / "cleaned" / "fifa_fbref_merged_processed_v2.csv"
LINK = ROOT / "data" / "external" / "tm_player_link.csv"
SKIPPED_PATH = ALIAS_PATH.with_name("player_id_alias_skipped.csv")

NATION_SPELLING = {"holland": "netherlands", "czechia": "czech republic", "turkiye": "turkey",
                   "korea republic": "south korea", "china pr": "china", "republic of ireland": "ireland",
                   "bosnia herzegovina": "bosnia and herzegovina", "cote d'ivoire": "ivory coast",
                   "curacao": "curacao", "united states": "usa"}


def _nat(value) -> str:
    key = fold(value)
    return NATION_SPELLING.get(key, key)


def propose() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(PROCESSED, low_memory=False)
    links = pd.read_csv(LINK, dtype={"player_id": str})
    shared = links[links["tm_id_shared"]]
    df["birth_est"] = df["season"].map(season_start_year) - df["age_fifa"]
    per_id = df.sort_values("season").groupby("player_id").agg(
        seasons=("season", lambda s: set(s)), rows=("season", "size"), last_season=("season", "max"),
        nat=("nationality_name", lambda s: s.dropna().iloc[-1] if s.notna().any() else ""),
        birth=("birth_est", "median"), height=("height_cm", "last"),
        names=("long_name", lambda s: set(s.dropna())),
    )
    aliases, skipped = [], []
    for tm_id, grp in shared.groupby("tm_player_id"):
        ids = list(grp["player_id"])
        info = per_id.loc[ids]
        reason = None
        if (grp["match_confidence"] != "High").any():
            reason = "link_not_high_confidence"
        elif any(a & b for i, a in enumerate(info["seasons"]) for b in list(info["seasons"])[i + 1:]):
            reason = "season_overlap"
        elif info["birth"].max() - info["birth"].min() > 1.01:
            reason = "birth_year_mismatch"
        else:
            toks = [set().union(*[fold(n).split() for n in names]) for names in info["names"]]
            if any(not (toks[0] & t) for t in toks[1:]):
                reason = "name_mismatch"
        kind = "nationality_spelling"
        if reason is None and len({_nat(n) for n in info["nat"]}) > 1:
            tm_h = grp["height_in_cm"].iloc[0]
            ok = pd.notna(tm_h) and all(pd.notna(h) and abs(h - tm_h) <= 3 for h in info["height"])
            if ok:
                kind = "nationality_change_height_verified"
            else:
                reason = "nationality_conflict_unverified"
        if reason:
            skipped.append({"tm_player_id": tm_id, "player_ids": "|".join(ids), "reason": reason})
            continue
        canon = info.sort_values(["rows", "last_season"], ascending=False).index[0]
        for pid in ids:
            if pid != canon:
                aliases.append({"alias_id": pid, "canonical_id": canon, "tm_player_id": tm_id, "reason": kind})
    return pd.DataFrame(aliases), pd.DataFrame(skipped)


if __name__ == "__main__":
    a, s = propose()
    ALIAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    a.to_csv(ALIAS_PATH, index=False)
    s.to_csv(SKIPPED_PATH, index=False)
    print(f"aliases proposed: {len(a)}  groups skipped: {len(s)}")
    print(a["reason"].value_counts().to_dict())
    print(s["reason"].value_counts().to_dict())
