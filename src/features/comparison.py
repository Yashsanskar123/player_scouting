"""Player comparison (spec section 34). Supports 2-5 players.

This is mostly data assembly, not a new model -- reuses whatever's
already been computed (performance score, potential, value, risk,
percentiles) rather than recomputing anything. The one piece of actual
logic is restructuring percentiles from "one row per player with N
percentile columns" into "one row per metric with one column per player,"
which is what a comparison table actually needs to render -- and only for
metrics that exist for ALL selected players, so the table never has a
row that's silently blank for someone.
"""
from __future__ import annotations

import pandas as pd

from src.utils import to_native

MAX_PLAYERS = 5
MIN_PLAYERS = 2


def compare_players(df: pd.DataFrame, player_ids: list[str]) -> dict:
    if not (MIN_PLAYERS <= len(player_ids) <= MAX_PLAYERS):
        raise ValueError(f"Comparison supports {MIN_PLAYERS}-{MAX_PLAYERS} players, got {len(player_ids)}.")
    if "player_id" not in df.columns:
        raise ValueError("df must have player_id assigned.")

    rows = {}
    for pid in player_ids:
        matches = df[df["player_id"] == pid]
        if matches.empty:
            raise ValueError(f"No player found with player_id '{pid}'.")
        rows[pid] = matches.sort_values("season").iloc[-1] if "season" in df.columns else matches.iloc[0]

    summary_cols = [
        "short_name", "canonical_position", "club_name", "league_name", "age_fifa",
        "value_eur", "fair_value_eur", "performance_score", "development_potential",
        "recruitment_risk_tier", "sample_reliability_score",
    ]
    players = []
    for pid in player_ids:
        row = rows[pid]
        entry = {"player_id": pid}
        for c in summary_cols:
            if c in row.index:
                entry[c] = to_native(row[c])
        players.append(entry)

    # Percentile comparison: only metrics present (non-null) for every
    # selected player, so the table has no silently-blank cells.
    pctile_cols = [c for c in df.columns if c.endswith("_pctile")]
    common_metrics = [c for c in pctile_cols if all(pd.notna(rows[pid].get(c)) for pid in player_ids)]

    percentile_comparison = []
    for c in common_metrics:
        label = c.replace("_pctile", "").replace("per_90_minutes_", "").replace("_", " ")
        percentile_comparison.append({
            "metric": label,
            "values": {pid: round(float(rows[pid][c]), 1) for pid in player_ids},
        })

    return {"players": players, "percentile_comparison": percentile_comparison}
