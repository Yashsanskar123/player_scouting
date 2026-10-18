"""Position- and season-aware percentile engine (spec section 10).

Raw per-90 numbers are meaningless without a peer group: a CB's tackles/90
means something different compared to other CBs than compared to the
whole league. This computes percentiles within configurable peer groups
and only among players who clear a minutes threshold, so a 200-minute
sample doesn't distort the peer distribution for everyone else.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# The per-90 / rate metrics percentiles are computed for. Kept to
# genuinely comparable rate stats -- never raw totals, which scale with
# minutes played.
PERCENTILE_METRICS = [
    "per_90_minutes_gls", "per_90_minutes_ast", "per_90_minutes_x_g", "per_90_minutes_x_ag",
    "per_90_minutes_npx_g", "per_90_minutes_prg_c", "per_90_minutes_prg_p", "per_90_minutes_prg_r",
    "per_90_minutes_kp", "per_90_minutes_1_3", "per_90_minutes_ppa", "per_90_minutes_crs_pa",
    "per_90_minutes_total_cmp", "total_cmppct", "per_90_minutes_expected_x_a",
    "per_90_minutes_tackles_tkl", "per_90_minutes_tackles_tkl_w", "per_90_minutes_int",
    "per_90_minutes_tkl_int", "per_90_minutes_clr", "per_90_minutes_blocks_blocks",
    "sca_sca90", "gca_gca90",
    "per_90_minutes_performance_saves", "performance_savepct", "performance_cspct",
]

MIN_MINUTES_FOR_PEER_GROUP = 900  # ~10 full matches; below this a player is scored but excluded as a peer


def compute_percentiles(
    df: pd.DataFrame,
    peer_group_cols: list[str] | None = None,
    metrics: list[str] | None = None,
) -> pd.DataFrame:
    """Add `<metric>_pctile` columns (0-100) computed within peer groups.

    Default peer group is (broad_position_group, season) so a CB in
    2023/24 is compared to other CBs in 2023/24, not to forwards or to a
    different season's talent pool.
    """
    df = df.copy()
    peer_group_cols = peer_group_cols or [c for c in ["broad_position_group", "season"] if c in df.columns]
    metrics = [m for m in (metrics or PERCENTILE_METRICS) if m in df.columns]

    if not peer_group_cols or not metrics:
        return df

    minutes = pd.to_numeric(df.get("playing_time_min", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    eligible_peer = minutes >= MIN_MINUTES_FOR_PEER_GROUP

    for metric in metrics:
        values = pd.to_numeric(df[metric], errors="coerce")
        pct_col = f"{metric}_pctile"
        df[pct_col] = pd.NA

        # Rank each player within their peer group, using ONLY eligible
        # peers to build the reference distribution, but scoring every
        # player (including low-minute ones) against that distribution.
        # Vectorized via searchsorted for speed (O(n log n) per group
        # instead of an O(n^2) pairwise comparison).
        grouped = df.assign(_val=values, _eligible=eligible_peer).groupby(peer_group_cols, dropna=False)

        for _, group in grouped:
            eligible_vals = np.sort(group.loc[group["_eligible"], "_val"].dropna().to_numpy())
            if len(eligible_vals) < 5:
                continue
            all_vals = group["_val"]
            valid_mask = all_vals.notna()
            ranks = np.searchsorted(eligible_vals, all_vals[valid_mask].to_numpy(), side="right")
            pct_scores = pd.Series(ranks / len(eligible_vals) * 100, index=all_vals[valid_mask].index)
            df.loc[pct_scores.index, pct_col] = pct_scores

    return df
